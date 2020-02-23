#! /usr/bin/env python3

# TODO:
# - merge with link-checker.py?
# - cache the status results in the database, limit the number of checks per URL per day (and week/month too)
# - per-domain whitelist for HTTP to HTTPS conversion (more suitable for link-checker.py, unless we need to compare the results for both requests)

import logging
import datetime

import requests
import mwparserfromhell

from ws.client import API, APIError
from ws.db.database import Database
from ws.interactive import edit_interactive, require_login, InteractiveQuit
import ws.ArchWiki.lang as lang
from ws.parser_helpers.wikicode import ensure_flagged_by_template, ensure_unflagged_by_template

logger = logging.getLogger(__name__)


class ExtlinkStatusChecker:
    def __init__(self, timeout, max_retries):
        self.timeout = timeout
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(max_retries=max_retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # valid URLs - 2xx
        self.cache_valid_urls = set()
        # invalid URLs - 4xx
        self.cache_invalid_urls = set()
        # indeterminate - 3xx, 5xx
        self.cache_indeterminate_urls = set()

        now = datetime.datetime.utcnow()
        self.deadlink_params = [now.year, now.month, now.day]
        self.deadlink_params = ["{:02d}".format(i) for i in self.deadlink_params]

    def check_extlink_status(self, wikicode, extlink):
        # make a copy of the URL object
        url = mwparserfromhell.parse(str(extlink.url))

        # replace HTML entities like "&#61" or "&Sigma;" with their unicode equivalents
        for entity in url.ifilter_html_entities(recursive=True):
            url.replace(entity, entity.normalize())

        url = str(url)

        # skip unsupported schemes
        if not url.lower().startswith("http://") and not url.lower().startswith("https://"):
            return
        # skip empty URLs
        if url.lower() in ["http://", "https://"]:
            return

        # TODO: blacklist domains which require javascript (e.g. code.google.com)

        logger.info("Checking link {} ...".format(extlink))

        # TODO: Do we need to query-encode or not? Also drop the fragment.
        status = self.check_url(url)
        if status is True:
            # TODO: the link might still be flagged for a reason (e.g. when the server redirects to some dummy page without giving a proper status code)
            ensure_unflagged_by_template(wikicode, extlink, "Dead link")
        elif status is False:
            # TODO: handle bbs.archlinux.org (some links may require login)
            # TODO: handle links inside {{man|url=...}} properly
            ensure_flagged_by_template(wikicode, extlink, "Dead link", *self.deadlink_params, overwrite_parameters=False)
        else:
            logger.warning("status check indeterminate for external link {}".format(extlink))

    def check_url(self, url):
        if url.startswith("ftp://"):
            logger.error("The FTP protocol is not supported by the requests module. URL: {}".format(url))
            return True
        if url in self.cache_valid_urls:
            return True
        elif url in self.cache_invalid_urls:
            return False
        elif url in self.cache_indeterminate_urls:
            return None

        try:
            response = self.session.head(url, timeout=self.timeout, allow_redirects=True)
        except requests.exceptions.ConnectionError as e:
            # TODO: how to handle DNS errors properly?
            if "name or service not known" in str(e).lower():
                self.cache_invalid_urls.add(url)
                return False
            # other connection error - indeterminate, do not cache
            return None
        except requests.exceptions.RequestException as e:
            # base class exception - indeterminate error, do not cache
            logger.exception("URL {} could not be checked due to {}".format(url, e))
            return None

        if response.status_code >= 200 and response.status_code < 300:
            self.cache_valid_urls.add(url)
            return True
        elif response.status_code >= 400 and response.status_code < 500:
            logger.error("status code {} for URL {}".format(response.status_code, url))
            self.cache_invalid_urls.add(url)
            return False
        else:
            logger.warning("status code {} for URL {}".format(response.status_code, url))
            # TODO: ask the user for manual check (good/bad/skip)
            self.cache_indeterminate_urls.add(url)
            return None


class Checker(ExtlinkStatusChecker):
    def __init__(self, api, db, first=None, title=None, langnames=None, connection_timeout=30, max_retries=3):
        # init inherited
        ExtlinkStatusChecker.__init__(self, connection_timeout, max_retries)

        # ensure that we are authenticated
        require_login(api)

        self.api = api
        self.db = db

        # parameters for self.run()
        self.first = first
        self.title = title
        self.langnames = langnames

        self.db.sync_with_api(api)
        self.db.sync_latest_revisions_content(api)
        self.db.update_parser_cache()

    @staticmethod
    def set_argparser(argparser):
        # first try to set options for objects we depend on
        present_groups = [group.title for group in argparser._action_groups]
        if "Connection parameters" not in present_groups:
            API.set_argparser(argparser)
        if "Database parameters" not in present_groups:
            Database.set_argparser(argparser)

        group = argparser.add_argument_group(title="script parameters")
        mode = group.add_mutually_exclusive_group()
        mode.add_argument("--first", default=None, metavar="TITLE",
                help="the title of the first page to be processed")
        mode.add_argument("--title",
                help="the title of the only page to be processed")
        group.add_argument("--lang", default=None,
                help="comma-separated list of language tags to process (default: all, choices: {})".format(lang.get_internal_tags()))

    @classmethod
    def from_argparser(klass, args, api=None, db=None):
        if api is None:
            api = API.from_argparser(args)
        if db is None:
            db = Database.from_argparser(args)
        if args.lang:
            tags = args.lang.split(",")
            for tag in tags:
                if tag not in lang.get_internal_tags():
                    # FIXME: more elegant solution
                    raise Exception("{} is not a valid language tag".format(tag))
            langnames = {lang.langname_for_tag(tag) for tag in tags}
        else:
            langnames = set()
        return klass(api, db, first=args.first, title=args.title, langnames=langnames, connection_timeout=args.connection_timeout, max_retries=args.connection_max_retries)

    def update_page(self, src_title, text):
        """
        Parse the content of the page and call various methods to update the links.

        :param str src_title: title of the page
        :param str text: content of the page
        :returns: a (text, edit_summary) tuple, where text is the updated content
            and edit_summary is the description of performed changes
        """
        logger.info("Parsing page [[{}]] ...".format(src_title))
        # FIXME: skip_style_tags=True is a partial workaround for https://github.com/earwig/mwparserfromhell/issues/40
        wikicode = mwparserfromhell.parse(text, skip_style_tags=True)

        for extlink in wikicode.ifilter_external_links(recursive=True):
            self.check_extlink_status(wikicode, extlink)

        edit_summary = "update status of external links (interactive)"
        return str(wikicode), edit_summary

    def _edit(self, title, pageid, text_new, text_old, timestamp, edit_summary):
        if text_old != text_new:
            try:
                # TODO: set bot="" only when the logged-in user is a bot
                edit_interactive(self.api, title, pageid, text_old, text_new, timestamp, edit_summary, bot="")
            except APIError as e:
                pass

    def process_page(self, title):
        result = self.api.call_api(action="query", prop="revisions", rvprop="content|timestamp", rvslots="main", titles=title)
        page = list(result["pages"].values())[0]
        timestamp = page["revisions"][0]["timestamp"]
        text_old = page["revisions"][0]["slots"]["main"]["*"]
        text_new, edit_summary = self.update_page(title, text_old)
        self._edit(title, page["pageid"], text_new, text_old, timestamp, edit_summary)

    def process_allpages(self, apfrom=None, langnames=None):
        namespaces = [0, 4, 12, 14]

        # rewind to the right namespace (the API throws BadTitle error if the
        # namespace of apfrom does not match apnamespace)
        if apfrom is not None:
            _title = self.api.Title(apfrom)
            if _title.namespacenumber not in namespaces:
                logger.error("Valid namespaces for the --first option are {}.".format([self.api.site.namespaces[ns] for ns in namespaces]))
                return
            while namespaces[0] != _title.namespacenumber:
                del namespaces[0]
            # apfrom must be without namespace prefix
            apfrom = _title.pagename

        for ns in namespaces:
            for page in self.db.query(generator="allpages", gaplimit="max", gapfilterredir="nonredirects", gapnamespace=ns, gapfrom=apfrom,
                                      prop="latestrevisions", rvprop={"timestamp", "content"}):
                title = page["title"]
                if langnames and lang.detect_language(title)[1] not in langnames:
                    continue
                _title = self.api.Title(title)
                timestamp = page["revisions"][0]["timestamp"]
                text_old = page["revisions"][0]["*"]
                text_new, edit_summary = self.update_page(title, text_old)
                self._edit(title, page["pageid"], text_new, text_old, timestamp, edit_summary)
            # the apfrom parameter is valid only for the first namespace
            apfrom = ""

    def run(self):
        if self.title is not None:
            checker.process_page(self.title)
        else:
            checker.process_allpages(apfrom=self.first, langnames=self.langnames)


if __name__ == "__main__":
    import ws.config

    checker = ws.config.object_from_argparser(Checker, description="Parse all pages on the wiki and try to fix/simplify/beautify links")

    try:
        checker.run()
    except (InteractiveQuit, KeyboardInterrupt):
        pass
