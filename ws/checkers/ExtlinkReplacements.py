#! /usr/bin/env python3

import re
import logging
import os.path
import json
import enum

import mwparserfromhell
import jinja2
from hstspreload import in_hsts_preload
import httpx

from .CheckerBase import CheckerBase, get_edit_summary_tracker
from .ExtlinkStatusChecker import ExtlinkStatusChecker
from .ExtlinkStatusUpdater import ExtlinkStatusUpdater
from .https_everywhere.rules import Ruleset
from .https_everywhere.rule_trie import RuleTrie
from .smarter_encryption_list import SmarterEncryptionList
from ws.utils import LazyProperty
from ws.parser_helpers.wikicode import ensure_unflagged_by_template
from ws.parser_helpers.encodings import querydecode

__all__ = ["ExtlinkReplacements"]

logger = logging.getLogger(__name__)

class ExtlinkReplacements(CheckerBase):

    class ExtlinkBehaviour(enum.Enum):
        # the extlink must not have any alternative text (but brackets are not checked)
        NO_TEXT = 1
        # the extlink must not have brackets (and hence also no alternative text)
        NO_BRACKETS = 2

    # list of (url_regex, text_cond, text_cond_flags, replacement) tuples, where:
    #   - url_regex: a regular expression matching the URL (using re.fullmatch)
    #   - text_cond:
    #       - as str: a format string used to create the regular expression for
    #                 matching the link's alternative text (it is formatted using
    #                 the groups matched by url_regex)
    #       - as ExtlinkBehaviour: special behaviour without an alternative text
    #                              (see the enum for details)
    #   - text_cond_flags: flags for the text_cond regex
    #   - replacement: a format string used as a replacement (it is formatted
    #                  using the groups matched by url_regex and the alternative
    #                  text (if present))
    extlink_replacements = [
        # Arch bug tracker
        (re.escape("https://bugs.archlinux.org/task/") + r"(\d+)",
            "(FS|flyspray) *#?{0}", 0, "{{{{Bug|{0}}}}}"),
        # URLs with brackets but without an alternative text should be left alone
        (re.escape("https://bugs.archlinux.org/task/") + r"(\d+)",
            ExtlinkBehaviour.NO_BRACKETS, 0, "{{{{Bug|{0}}}}}"),

        # exclude the replacement of some links using pkgbase - see [[Firefox]]
        (r"https:\/\/archlinux.org\/packages\/extra\/(?:any)/(firefox-i18n)\/",
            "{0}", re.IGNORECASE, "[https://archlinux.org/packages/extra/any/firefox-i18n/ {0}]"),
        (r"https:\/\/archlinux.org\/packages\/community\/(?:any)\/(firefox-developer-edition-i18n)\/?",
            "{0}", re.IGNORECASE, "[https://archlinux.org/packages/community/any/firefox-developer-edition-i18n/ {0}]"),

        # official packages, with and without alternative text
        (r"https?\:\/\/(?:www\.)?archlinux\.org\/packages\/[\w-]+\/(?:any|i686|x86_64)\/([a-zA-Z0-9@._+-]+)\/?",
            "{0}", re.IGNORECASE, "{{{{Pkg|{0}}}}}"),
        (r"https?\:\/\/(?:www\.)?archlinux\.org\/packages\/[\w-]+\/(?:any|i686|x86_64)\/([a-zA-Z0-9@._+-]+)\/?",
            ExtlinkBehaviour.NO_TEXT, 0, "{{{{Pkg|{0}}}}}"),

        # AUR packages, with and without alternative text
        (r"https?\:\/\/aur\.archlinux\.org\/packages\/([a-zA-Z0-9@._+-]+)\/?",
            "{0}", re.IGNORECASE, "{{{{AUR|{0}}}}}"),
        (r"https?\:\/\/aur\.archlinux\.org\/packages\/([a-zA-Z0-9@._+-]+)\/?",
            ExtlinkBehaviour.NO_TEXT, 0, "{{{{AUR|{0}}}}}"),

        # Wikipedia interwiki
        (r"https?\:\/\/en\.wikipedia\.org\/wiki\/([^\]\?]+)",
            ".*", 0, "[[Wikipedia:{0}|{1}]]"),
        (r"https?\:\/\/en\.wikipedia\.org\/wiki\/([^\]\?]+)",
            ExtlinkBehaviour.NO_TEXT, 0, "[[Wikipedia:{0}]]"),

        # international Wikipedia links
        (r"https?:\/\/([a-z]+?)\.wikipedia\.org\/wiki\/([^\]\?]+)",
            ".+", 0, "[[Wikipedia:{0}:{1}|{2}]]"),
        (r"https?:\/\/([a-z]+?)\.wikipedia\.org\/wiki\/([^\]\?]+)",
            ExtlinkBehaviour.NO_TEXT, 0, "[[Wikipedia:{0}:{1}]]"),
    ]

    # list of (edit_summary, url_regex, url_replacement) tuples, where:
    #   - edit_summary: a string with the edit summary to use for this replacement
    #   - url_regex: a regular expression matching the URL (using re.fullmatch)
    #   - url_replacement: a format string used as a replacement for the URL
    #       (it is formatted using the groups matched by url_regex). The string
    #       must be formatted as a Jinja2 template: named groups are passed as
    #       variables, unnamed groups are in a special variable "m" and can be
    #       accessed as {{m[0]}}, {{m[1]}} and so on. See the template language
    #       documentation for details:
    #       https://jinja.palletsprojects.com/en/2.11.x/templates/
    # Note that this replaces URLs with URLs, in extlinks with or without an
    # alternative text. It is not possible to change extlink to other node type
    # such as wikilink here.
    url_replacements = [
        # Archweb

        # people
        ("update old archweb people URLs to archlinux.org/people/",
         r"https?\:\/\/(?:www\.)?archlinux\.org\/(?P<group>developers|fellows|trustedusers)\/(?P<person>#.+)?",
            "https://archlinux.org/people/{{group | replace ('fellows', 'developer-fellows') | replace('trustedusers', 'trusted-users')}}/{% if person is not none %}{{person}}{% endif %}"),

        # mailman
        ("update old mailman URLs from (lists|mailman).archlinux.org/listinfo/ to lists.archlinux.org/mailman3/lists/",
            r"https?\:\/\/(?:lists\.|mailman\.|www\.)?archlinux\.org(\/mailman)?\/\/?listinfo(?P<mailinglist>\/[\w-]+)?\/?",
            "https://lists.archlinux.org/mailman3/lists{% if mailinglist is not none %}{{mailinglist}}.lists.archlinux.org{% endif %}/"),
        ("update old mailman URLs from (lists|mailman).archlinux.org/pipermail/ to lists.archlinux.org/archives/",
            r"https?\:\/\/(?:lists\.|mailman\.|www\.)?archlinux\.org\/pipermail(?P<mailinglist>\/[\w-]+)?\/?",
            "https://lists.archlinux.org/archives/{% if mailinglist is not none %}list{{mailinglist}}@lists.archlinux.org/{% endif %}"),

        # ancient php pages
        ("update ancient archweb URLs from archlinux.org/*.php to archlinux.org/*/",
            r"https?\:\/\/(?:www\.)?archlinux\.org\/(?P<page>.+?)\.php",
            "https://archlinux.org/{{page}}/"),

        # Archweb
        ("update archweb URLs from www.archlinux.org to archlinux.org",
            r"https?\:\/\/www\.archlinux\.org(?P<path>\/.*)?",
            "https://archlinux.org{% if path is not none %}{{path}}{% endif %}"),

        # aurweb
        ("remove .php from aurweb URLs",
            r"https?\:\/\/aur\.archlinux\.org\/(?P<path>packages|rpc|index)\.php\/?(?P<params>.*)?",
            "https://aur.archlinux.org/{% if path != 'index' %}{{path}}{% endif %}{% if params is not none %}{{params}}{% endif %}"),

        # migration of Arch's git URLs

        # svntogit commits
        ("update svntogit URLs from (projects|git).archlinux.org to github.com",
            r"https?\:\/\/(?:projects|git)\.archlinux\.org\/svntogit\/(?P<repo>packages|community)\.git\/commit\/(?P<path>[^?]+?)?(?:\?h=[^&#?]+?)?(?:[&?]id=(?P<commit>[0-9A-Fa-f]+))",
            "https://github.com/archlinux/svntogit-{{repo}}/commit/{{commit}}{% if (path is not none) and ('/' in path) %}/{{path}}{% endif %}"),
        # svntogit blobs, raws and logs
        ("update svntogit URLs from (projects|git).archlinux.org to github.com",
            r"https?\:\/\/(?:projects|git)\.archlinux\.org\/svntogit\/(?P<repo>packages|community)\.git\/(?P<type>tree|plain|log)\/(?P<path>[^?]+?)(?:\?h=(?P<branch>[^&#?]+?))?(?:[&?]id=(?P<commit>[0-9A-Fa-f]+))?(?:#n(?P<linenum>\d+))?",
            "https://github.com/archlinux/svntogit-{{repo}}/{{type | replace('tree', 'blob') | replace('plain', 'raw') | replace('log', 'commits')}}/{% if commit is not none %}{{commit}}/{% elif branch is not none %}{{branch}}/{% elif (path is not none) and (not path.startswith('packages')) %}packages/{% endif %}{{path}}{% if linenum is not none %}#L{{linenum}}{% endif %}"),
        # svntogit repos
        ("update svntogit URLs from (projects|git).archlinux.org to github.com",
            r"https?\:\/\/(?:projects|git)\.archlinux\.org\/svntogit\/(?P<repo>packages|community)\.git(\/tree)?\/?",
            "https://github.com/archlinux/svntogit-{{repo}}"),

        # other git repos
        ("update old (projects|git).archlinux.org links",
            r"https?\:\/\/(?:projects|git)\.archlinux\.org\/(?P<project>abs|archboot|archiso|aurweb|infrastructure|initscripts|mkinitcpio|namcap|netcfg|netctl|pacman|srcpac).git(?:\/(?P<type>commit|tree|plain|log))?(?P<path>[^?]+?)?(?:\?h=(?P<branch>[^&#?]+?))?(?:[&?]id=(?P<commit>[0-9A-Ha-f]+))?(?:#n(?P<linenum>\d+))?",
            "https://gitlab.archlinux.org/{% if project == 'archboot' %}tpowa{% elif project in [ 'pacman', 'namcap' ] %}pacman{% else %}archlinux{% endif %}{% if project == 'mkinitcpio' %}/mkinitcpio{% endif %}/{{project}}{% if type is not none %}/{{type | replace('plain', 'raw') | replace('log', 'commits')}}{% if commit is not none %}/{{commit}}{% elif branch is not none %}/{{branch}}{% elif path is not none %}/master{% endif %}{% if (path is not none) and (path != '/') %}{{path}}{% endif %}{% if linenum is not none %}#L{{linenum}}{% endif %}{% endif %}"),
        ("update old (projects|git).archlinux.org links",
            r"https?\:\/\/(?:projects|git)\.archlinux\.org\/(?P<project>arch-install-scripts|archweb|dbscripts|devtools|linux|vhosts\/wiki\.archlinux\.org).git(?:\/(?P<type>commit|tree|plain|log))?(?P<path>[^?]+?)?(?:\?h=(?P<branch>[^&#?]+?))?(?:[&?]id=(?P<commit>[0-9A-Ha-f]+))?(?:#n(?P<linenum>\d+))?",
            "https://github.com/archlinux/{{project | replace ('vhosts/wiki.archlinux.org', 'archwiki')}}{% if type is not none %}/{{type | replace('plain', 'raw') | replace('log', 'commits')}}{% if commit is not none %}/{{commit}}{% elif branch is not none %}/{{branch}}{% elif path is not none %}/master{% endif %}{% if (path is not none) and (path != '/') %}{{path}}{% endif %}{% if linenum is not none %}#L{{linenum}}{% endif %}{% endif %}"),

        # projects that moved from github.com/archlinux/ or are mirrored there
        ("change Arch project URLs from github.com to gitlab.archlinux.org",
             r"https?\:\/\/github\.com\/archlinux\/(?P<repo>arch-boxes|arch-historical-archive|arch-install-scripts|arch-rebuild-order|arch-repo-management|arch-signoff|archbbs|archiso|archivetools|asknot-ng|conf\.archlinux\.org|mkinitcpio|rebuilder|sandcrawler|signstar)(?P<git>\.git)?",
             "https://gitlab.archlinux.org/archlinux/{% if repo == 'mkinitcpio' %}mkinitcpio/{% endif %}{{repo | replace ('conf.archlinux.org', 'conf') | replace ('rebuilder' , 'arch-rebuild-order')}}{% if git is not none %}{{git}}{% endif %}"),
        ("change Arch project URLs from github.com to gitlab.archlinux.org",
             r"https?\:\/\/github\.com\/archlinux\/(?P<repo>arch-boxes|arch-historical-archive|arch-install-scripts|arch-rebuild-order|arch-repo-management|arch-signoff|archbbs|archiso|archivetools|asknot-ng|conf\.archlinux\.org|mkinitcpio|rebuilder|sandcrawler|signstar)(?:\.git)?\/commit\/(?P<commit>[0-9A-Fa-f]+)",
             "https://gitlab.archlinux.org/archlinux/{% if repo == 'mkinitcpio' %}mkinitcpio/{% endif %}{{repo | replace ('conf.archlinux.org', 'conf') | replace ('rebuilder' , 'arch-rebuild-order')}}/commit/{{commit}}"),
        # TODO: blobs, history (/commits/), raw (including raw.githubusercontent.com)
        # NOTE: for line selection GitHub uses #L10-L15 while GitLab uses #L10-15

        # update addons.mozilla.org and addons.thunderbird.net
        ("remove language codes from addons.mozilla.org and addons.thunderbird.net links",
            r"https?\:\/\/addons\.(?:mozilla\.org|thunderbird\.net)/[^/]+?\/(?P<application>firefox|android|thunderbird|seamonkey)(?P<path>.+)?",
            "https://addons.{% if application in [ 'thunderbird', 'seamonkey' ] %}thunderbird.net{% else %}mozilla.org{% endif %}/{{application}}{% if path is not none %}{{path}}{% endif %}"),
        ("update links from addons.mozilla.org to addons.thunderbird.net",
            r"https?\:\/\/addons\.mozilla\.org/(?P<application>thunderbird|seamonkey)(?P<path>.+)?",
            "https://addons.thunderbird.net/{{application}}{% if path is not none %}{{path}}{% endif %}"),

        # kernel.org documentation links
        ("link to HTML version of kernel documentation",
            r"https?\:\/\/(?:www\.)?kernel.org/doc/Documentation(?P<path>\/.+?)(?P<extension>\.txt|\.rst)?",
            "https://docs.kernel.org{{path}}{% if extension is not none %}.html{% endif %}"),
        ("link to the kernel documentation on docs.kernel.org",
            r"https?\:\/\/(?:www\.)?kernel\.org\/doc\/html\/[^\/]+(?P<path>\/.*)?",
            "https://docs.kernel.org{% if path is not none %}{{path}}{% endif %}"),

        # wireless.wiki.kernel.org
        ("update linuxwireless.org/wireless.kernel.org links",
            r"https?\:\/\/(?:(?:www\.)?linuxwireless|wireless\.kernel)\.org/(?P<path>[^#]*)(?P<fragment>#.+)?",
            "https://wireless.wiki.kernel.org/{{path | lower}}{% if fragment is not none %}{{fragment | lower}}{% endif %}"),

        # Stack Exchange short links
        ("remove user IDs from short links to Stack Exchange posts",
            r"https?\:\/\/(?P<domain>(?:\w+\.)?stackexchange\.com|stackoverflow\.com|askubuntu\.com|serverfault\.com|superuser\.com|mathoverflow\.net)\/a\/(?P<answer>\d+)\/\d+",
            "https://{{domain}}/a/{{answer}}"),

        # IRC links
        # note: old links may use "#" or "/#" instead of "/" as the separator
        # note: using "#" unescaped in the URL (as part of the channel name) is discouraged,
        #       there are even channel names starting with "##" (but we are not matching that)
        ("update links for IRC channels that left Freenode (if a particular channel is not on Libera, please fix it manually)",
            r"ircs?\:\/\/\w+\.freenode\.net(\/#|\/|#)(?P<channel>archlinux.*|bash)",
            "ircs://irc.libera.chat/{{channel}}"),
        ("replace irc:// with ircs:// for networks that support it",
            r"ircs?\:\/\/(?P<domain>\w+\.freenode\.net|irc\.libera\.chat|irc\.oftc\.net|irc\.rizon\.net|irc\.azzurra\.org)(?P<path>\/.*)?",
            "ircs://{{domain}}{% if (path is not none) %}{{path}}{% endif %}"),

        # TODO: use Special:Permalink on ArchWiki: https://wiki.archlinux.org/index.php?title=Pacman/Tips_and_tricks&diff=next&oldid=630006
    ]

    https_everywhere_rules_path = os.path.join(os.path.dirname(__file__), "https_everywhere/default.rulesets.json")
    https_everywhere_rules = None

    def __init__(self, api, db=None, **kwargs):
        super().__init__(api, db, **kwargs)

        _extlink_replacements = []
        for url_regex, text_cond, text_cond_flags, replacement in self.extlink_replacements:
            compiled = re.compile(url_regex)
            _extlink_replacements.append( (compiled, text_cond, text_cond_flags, replacement) )
        self.extlink_replacements = _extlink_replacements

        _url_replacements = []
        for edit_summary, url_regex, url_replacement in self.url_replacements:
            compiled = re.compile(url_regex)
            _url_replacements.append( (edit_summary, compiled, url_replacement) )
        self.url_replacements = _url_replacements

        # initialize HTTPS Everywhere rules as a klass (static) attribute, because it is rather expensive
        # (note that the class is initialized many times in tests)
        if ExtlinkReplacements.https_everywhere_rules is None:
            ExtlinkReplacements.https_everywhere_rules = RuleTrie()
            data = json.load(open(self.https_everywhere_rules_path, "r"))
            for r in data:
                ruleset = Ruleset(r, "<unknown file>")
                if ruleset.defaultOff:
                    logging.debug("Skipping HTTPS Everywhere rule '{}', reason: {}".format(ruleset.name, ruleset.defaultOff))
                    continue
                self.https_everywhere_rules.addRuleset(ruleset)

        # pass timeout and max_retries
        self.selist = SmarterEncryptionList(**kwargs)
        assert "wiki.archlinux.org" in self.selist
        assert "foo" not in self.selist

    @LazyProperty
    def wikisite_extlink_regex(self):
        general = self.api.site.general
        regex = re.escape(general["server"] + general["articlepath"].split("$1")[0])
        regex += r"(?P<pagename>[^\s\?]+)"
        return re.compile(regex)

    @staticmethod
    def strip_extra_brackets(wikicode, extlink):
        """
        Strip extra brackets around an external link, for example:

            [[http://example.com/ foo]] -> [http://example.com/ foo]
        """
        parent, _ = wikicode._do_strong_search(extlink, True)
        index = parent.index(extlink)

        def _get_text(index):
            try:
                node = parent.get(index)
                if not isinstance(node, mwparserfromhell.nodes.text.Text):
                    return None
                return node
            except IndexError:
                return None

        prev = _get_text(index - 1)
        next_ = _get_text(index + 1)

        if prev is not None and next_ is not None and prev.endswith("[") and next_.startswith("]"):
            prev.value = prev.value[:-1]
            next_.value = next_.value[1:]

    def check_extlink_to_wikilink(self, wikicode, extlink, url: str):
        match = self.wikisite_extlink_regex.fullmatch(url)
        if match:
            pagename = match.group("pagename")
            title = self.api.Title(pagename)
            target = title.format(iwprefix=True, namespace=True, sectionname=True)
            # handle links to special namespaces correctly
            if title.namespacenumber in {-2, 6, 14}:
                target = ":" + target
            if extlink.title:
                wikilink = "[[{}|{}]]".format(target, extlink.title)
            else:
                wikilink = "[[{}]]".format(target)
            wikicode.replace(extlink, wikilink)
            # TODO: what if the extlink was flagged with Dead link?
            return True
        return False

    def check_extlink_replacements(self, wikicode, extlink, url: str):
        repl = None

        for url_regex, text_cond, text_cond_flags, replacement in self.extlink_replacements:
            assert text_cond is not None
            # regex requires extlink.title
            if isinstance(text_cond, str) and extlink.title is None:
                continue
            # all enum values of ExtlinkBehaviour require extlink.title to be None
            if isinstance(text_cond, self.ExtlinkBehaviour) and extlink.title is not None:
                continue
            # check ExtlinkBehaviour.NO_BRACKETS
            if text_cond == self.ExtlinkBehaviour.NO_BRACKETS and extlink.brackets:
                continue
            # decode unicode characters in the URL before matching
            try:
                decoded_url = querydecode(url)
            except UnicodeDecodeError:
                continue
            match = url_regex.fullmatch(decoded_url)
            if match:
                if extlink.title is None:
                    repl = replacement.format(*match.groups())
                    break
                else:
                    groups = [re.escape(g) for g in match.groups()]
                    alt_text = str(extlink.title).strip()
                    if re.fullmatch(text_cond.format(*groups), alt_text, text_cond_flags):
                        repl = replacement.format(*match.groups(), extlink.title)
                        break
                    else:
                        logger.warning("external link that should be replaced, but has custom alternative text: {}".format(extlink))

        if repl is None:
            # no replacement found
            return False
        elif repl == str(extlink):
            # some replacements are intended to actually avoid a change in the wikicode
            return False
        else:
            # we have a replacement that changes the wikicode
            wikicode.replace(extlink, repl)
            # TODO: make sure that the link is unflagged after replacement
            return True

    def check_url_replacements(self, wikicode, extlink, url: str):
        for edit_summary, url_regex, url_replacement in self.url_replacements:
            match = url_regex.fullmatch(url)
            if match:
                env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True)
                template = env.from_string(url_replacement)
                new_url = template.render(m=match.groups(), **match.groupdict())

                # check if the resulting URL is valid
                # (irc:// and ircs:// cannot be validated - requests throws requests.exceptions.InvalidSchema)
                if not new_url.startswith("irc://") and not new_url.startswith("ircs://") and not ExtlinkStatusChecker.check_url_sync(new_url):
                    logger.warning("URL not replaced: {}".format(url))
                    return False

                # post-processing for gitlab.archlinux.org links
                #   - gitlab uses "blob" for files and "tree" for directories
                #   - if "blob" or "tree" is used incorrectly, gitlab gives 302 to the correct one
                #     (so we should replace new_url with what gitlab gives us)
                #   - the "/-/" disambiguator (which is added by gitlab's redirects) is ugly and should be removed thereafter
                #   - gitlab gives 302 to the master branch instead of 404 for non-existent files/directories
                if new_url.startswith("https://gitlab.archlinux.org"):
                    # use same query as ExtlinkStatusChecker.check_url_sync
                    with httpx.stream("GET", new_url, follow_redirects=True) as response:
                        # nothing to do here, but using the context manager ensures that the response is
                        # always properly closed
                        pass
                    if len(response.history) > 0:
                        if response.url.endswith("/master"):
                            # this is gitlab's "404" in most cases
                            logger.warning("URL not replaced (Gitlab redirected to a master branch): {}".format(url))
                            return False
                        new_url = response.url
                    new_url = new_url.replace("/-/", "/", 1)

                # some patterns match even the target
                # (e.g. links on addons.mozilla.org which already do not have a language code)
                if url == new_url:
                    return False

                extlink.url = new_url
                ensure_unflagged_by_template(wikicode, extlink, "Dead link", match_only_prefix=True)
                return edit_summary
        return False

    def check_http_to_https(self, wikicode, extlink, url: str):
        url = httpx.URL(url)

        if url.scheme != "http":
            return

        # check HSTS preload list first
        # (Chromium's static list of sites supporting HTTP Strict Transport Security)
        if in_hsts_preload(url.netloc.decode("utf-8").lower()):
            new_url = str(extlink.url).replace("http://", "https://", 1)
        # check HTTPS Everywhere rules next
        elif self.https_everywhere_rules.matchingRulesets(url.netloc.decode("utf-8").lower()):
            match = self.https_everywhere_rules.transformUrl(url)
            new_url = match.url
        # check the Smarter Encryption list
        elif url.netloc.decode("utf-8").lower() in self.selist:
            new_url = str(extlink.url).replace("http://", "https://", 1)
        else:
            return

        # there is no reason to update broken links
        if ExtlinkStatusChecker.check_url_sync(new_url):
            extlink.url = new_url
        else:
            logger.warning("broken URL not updated to https: {}".format(url))

    def update_extlink(self, wikicode, extlink, summary_parts):
        # prepare URL - fix parsing of adjacent templates, replace HTML entities, parse with urllib3
        url = ExtlinkStatusUpdater.prepare_url(wikicode, extlink)
        if url is None:
            return
        # check if the URL is checkable
        if not ExtlinkStatusChecker.is_checkable_url(url, allow_schemes=["http", "https", "irc", "ircs"]):
            return

        summary = get_edit_summary_tracker(wikicode, summary_parts)

        # FIXME: this can break templates because of "=", e.g. https://wiki.archlinux.org/index.php?title=Systemd_(Espa%C3%B1ol)/User_(Espa%C3%B1ol)&diff=629483&oldid=617318
        # see https://wiki.archlinux.org/index.php/User:Lahwaacz/Notes#Double_brackets_escape_template-breaking_characters
        with summary("removed extra brackets"):
            self.strip_extra_brackets(wikicode, extlink)

        # always make sure to return as soon as the extlink is matched and replaced
        with summary("replaced external links"):
            if self.check_extlink_to_wikilink(wikicode, extlink, url):
                return
            # TODO: HTML entities were replaced, templates may break if the decoded "&#61" stays in the replaced URL
            if self.check_extlink_replacements(wikicode, extlink, url):
                return

        # URL replacements use separate edit summaries
        es = self.check_url_replacements(wikicode, extlink, url)
        if es:
            summary_parts.append(es)
            return

        # this is run as the last step to avoid an unnecessary edit summary in
        # case a http link matches a previous replacement rule
        with summary("update http to https"):
            self.check_http_to_https(wikicode, extlink, url)

    def handle_node(self, src_title, wikicode, node, summary_parts):
        if isinstance(node, mwparserfromhell.nodes.ExternalLink):
            self.update_extlink(wikicode, node, summary_parts)
