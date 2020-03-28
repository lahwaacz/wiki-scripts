#! /usr/bin/env python3

# TODO:
# - merge with link-checker.py?
# - cache the status results in the database, limit the number of checks per URL per day (and week/month too)
# - per-domain whitelist for HTTP to HTTPS conversion (more suitable for link-checker.py, unless we need to compare the results for both requests)
# - GRRR: When you get 404, unless you have Javascript enabled, in which case the code loaded on the 404 page might execute a redirection to a different address. Example: https://nzbget.net/Performance_tips

import logging
import datetime
import ipaddress
import asyncio
from concurrent.futures import ThreadPoolExecutor

import requests
import requests.packages.urllib3 as urllib3
import mwparserfromhell

from ws.client import API, APIError
from ws.db.database import Database
from ws.interactive import edit_interactive, require_login, InteractiveQuit
import ws.ArchWiki.lang as lang
from ws.parser_helpers.wikicode import get_parent_wikicode, ensure_flagged_by_template, ensure_unflagged_by_template

logger = logging.getLogger(__name__)


class ExtlinkStatusChecker:
    def __init__(self, timeout, max_retries):
        self.timeout = timeout
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(max_retries=max_retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self.headers = {
            # fake user agent to bypass servers responding differently or not at all to non-browser user agents
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.116 Safari/537.36",
        }

        # valid URLs - 2xx
        self.cache_valid_urls = set()
        # invalid URLs - 4xx, domain resolution errors, etc. - mapping of the URL to status text
        self.cache_invalid_urls = {}
        # indeterminate - 3xx, 5xx
        self.cache_indeterminate_urls = set()

        now = datetime.datetime.utcnow()
        self.deadlink_params = [now.year, now.month, now.day]
        self.deadlink_params = ["{:02d}".format(i) for i in self.deadlink_params]

    def check_extlink_status(self, wikicode, extlink):
        # make a copy of the URL object (the skip_style_flags parameter is False,
        # so we will also properly parse URLs terminated by a wiki markup)
        url = mwparserfromhell.parse(str(extlink.url))

        # mwparserfromhell parses free URLs immediately followed by a template
        # (e.g. http://domain.tld/{{Dead link|2020|02|20}}) completely as one URL,
        # so we need to split it manually
        if "{{" in str(url):
            url, rest = str(url).split("{{", maxsplit=1)
            rest = "{{" + rest
            url = mwparserfromhell.parse(url)
            # remove everything after the real URL from the extlink...
            for node in extlink.url.nodes[1:]:
                extlink.url.remove(node)
            # ...and insert it into the parent wikicode after the link
            parent = get_parent_wikicode(wikicode, extlink)
            parent.insert_after(extlink, rest)

        # replace HTML entities like "&#61" or "&Sigma;" with their unicode equivalents
        for entity in url.ifilter_html_entities(recursive=True):
            url.replace(entity, entity.normalize())

        try:
            # try to parse the URL - fails e.g. if port is not a number
            # reference: https://urllib3.readthedocs.io/en/latest/reference/urllib3.util.html#urllib3.util.parse_url
            url = urllib3.util.url.parse_url(str(url))
        except urllib3.exceptions.LocationParseError:
            logger.debug("skipped invalid URL: {}".format(url))
            return

        # skip unsupported schemes
        if url.scheme not in ["http", "https"]:
            logger.debug("skipped URL with unsupported scheme: {}".format(url))
            return
        # skip URLs with empty host, e.g. "http://" or "http://git@" or "http:///var/run"
        # (partial workaround for https://github.com/earwig/mwparserfromhell/issues/196 )
        if not url.host:
            logger.debug("skipped URL with empty host: {}".format(url))
            return
        # skip links with top-level domains only
        # (in practice they would be resolved relative to the local domain, on the wiki they are used
        # mostly as a pseudo-variable like http://server/path or http://mydomain/path)
        if "." not in url.host:
            logger.debug("skipped URL with only top-level domain host: {}".format(url))
            return
        # skip links to localhost
        if url.host == "localhost" or url.host.endswith(".localhost"):
            logger.debug("skipped URL to localhost: {}".format(url))
            return
        # skip links to 127.*.*.* and ::1
        try:
            addr = ipaddress.ip_address(url.host)
            local_network = ipaddress.ip_network("127.0.0.0/8")
            if addr in local_network:
                logger.debug("skipped URL to local IP address: {}".format(url))
                return
        except ValueError:
            pass
        # drop the fragment from the URL (to optimize caching)
        if url.fragment:
            url = urllib3.util.url.parse_url(url.url.rsplit("#", maxsplit=1)[0])

        logger.info("Checking link {} ...".format(extlink))

        status = self.check_url(url)
        if status is True:
            # TODO: the link might still be flagged for a reason (e.g. when the server redirects to some dummy page without giving a proper status code)
            ensure_unflagged_by_template(wikicode, extlink, "Dead link")
        elif status is False:
            # TODO: handle bbs.archlinux.org (some links may require login)
            # TODO: handle links inside {{man|url=...}} properly
            # flag the link, but don't overwrite date and don't set status yet
            flag = ensure_flagged_by_template(wikicode, extlink, "Dead link", *self.deadlink_params, overwrite_parameters=False)
            # overwrite by default, but skip overwriting date when the status matches
            overwrite = True
            if flag.has("status"):
                status = flag.get("status")
                if str(status) == str(self.cache_invalid_urls[url]):
                    overwrite = False
            if overwrite is True:
                # overwrite status as well as date
                flag.add("status", self.cache_invalid_urls[url], showkey=True)
                flag.add("1", self.deadlink_params[0], showkey=False)
                flag.add("2", self.deadlink_params[1], showkey=False)
                flag.add("3", self.deadlink_params[2], showkey=False)
        else:
            # TODO: ask the user for manual check (good/bad/skip) and move the URL from self.cache_indeterminate_urls to self.cache_valid_urls or self.cache_invalid_urls
            logger.warning("status check indeterminate for external link {}".format(extlink))

    def check_url(self, url):
        if url in self.cache_valid_urls:
            return True
        elif url in self.cache_invalid_urls:
            return False
        elif url in self.cache_indeterminate_urls:
            return None

        try:
            # We need to use GET requests instead of HEAD, because many servers just return 404
            # (or do not reply at all) to HEAD requests. Instead, we skip the downloading of the
            # response body content using the ``stream=True`` parameter.
            response = self.session.get(url, headers=self.headers, timeout=self.timeout, stream=True)
        # SSLError inherits from ConnectionError so it has to be checked first
        except requests.exceptions.SSLError as e:
            logger.error("SSLError ({}) for URL {}".format(e, url))
            self.cache_invalid_urls[url] = "SSL error"
            return False
        except requests.exceptions.ConnectionError as e:
            # TODO: how to handle DNS errors properly?
            if "name or service not known" in str(e).lower():
                logger.error("domain name could not be resolved for URL {}".format(url))
                self.cache_invalid_urls[url] = "domain name not resolved"
                return False
            # other connection error - indeterminate, do not cache
            return None
        except requests.exceptions.TooManyRedirects as e:
            logger.error("TooManyRedirects error ({}) for URL {}".format(e, url))
            self.cache_invalid_urls[url] = "too many redirects"
            return False
        except requests.exceptions.RequestException as e:
            # base class exception - indeterminate error, do not cache
            logger.exception("URL {} could not be checked due to {}".format(url, e))
            return None

        if response.status_code >= 200 and response.status_code < 300:
            self.cache_valid_urls.add(url)
            return True
        elif response.status_code >= 400 and response.status_code < 500:
            logger.error("status code {} for URL {}".format(response.status_code, url))
            self.cache_invalid_urls[url] = response.status_code
            return False
        else:
            logger.warning("status code {} for URL {}".format(response.status_code, url))
            self.cache_indeterminate_urls.add(url)
            return None


class Checker(ExtlinkStatusChecker):
    def __init__(self, api, db, first=None, title=None, langnames=None, connection_timeout=60, max_retries=3):
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
        self.db.sync_revisions_content(api, mode="latest")
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
        group.add_argument("--lang", default="en",
                help="comma-separated list of language tags to process (default: en, choices: {})".format(lang.get_internal_tags()))

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

    async def update_page(self, src_title, text):
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

        # We could use the default single-threaded executor with basically the same performance
        # (because of Python's GIL), but the ThreadPoolExecutor allows to limit the maximum number
        # of workers and thus the maximum number of concurrent connections.
        with ThreadPoolExecutor(max_workers=10) as executor:
            with requests.Session() as session:
                loop = asyncio.get_event_loop()
                tasks = [
                    loop.run_in_executor(
                        executor,
                        self.check_extlink_status,
                        # a way to pass multiple arguments to the check_extlink_status method
                        *(wikicode, extlink)
                    )
                    for extlink in wikicode.ifilter_external_links(recursive=True)
                ]
                for result in await asyncio.gather(*tasks):
                    pass

        edit_summary = "update status of external links (interactive)"
        return str(wikicode), edit_summary

    def _edit(self, title, pageid, text_new, text_old, timestamp, edit_summary):
        if text_old != text_new:
            # print the info message
            print("\nSuggested edit for page [[{}]]. Please double-check all changes before accepting!".format(title))

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
        text_new, edit_summary = asyncio.run(self.update_page(title, text_old))
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
                text_new, edit_summary = asyncio.run(self.update_page(title, text_old))
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
