#! /usr/bin/env python3

import re
import logging
import os.path
import json

import mwparserfromhell
import jinja2
from hstspreload import in_hsts_preload

from .CheckerBase import get_edit_summary_tracker
from .ExtlinkStatusChecker import ExtlinkStatusChecker
from .https_everywhere.rules import Ruleset
from .https_everywhere.rule_trie import RuleTrie
from ws.utils import LazyProperty
from ws.parser_helpers.wikicode import ensure_unflagged_by_template

__all__ = ["ExtlinkReplacements"]

logger = logging.getLogger(__name__)

class ExtlinkReplacements(ExtlinkStatusChecker):

    # list of (url_regex, text_cond, text_cond_flags, replacement) tuples, where:
    #   - url_regex: a regular expression matching the URL (using re.fullmatch)
    #   - text_cond:
    #       - as str: a format string used to create the regular expression described above
    #                 (it is formatted using the groups matched by url_regex)
    #       - as None: the extlink must not have any alternative text
    #   - text_cond_flags: flags for the text_cond regex
    #   - replacement: a format string used as a replacement (it is formatted
    #                  using the groups matched by url_regex and the alternative
    #                  text (if present))
    extlink_replacements = [
        # Arch bug tracker
        (re.escape("https://bugs.archlinux.org/task/") + r"(\d+)",
            "(FS|flyspray) *#?{0}", 0, "{{{{Bug|{0}}}}}"),
        (re.escape("https://bugs.archlinux.org/task/") + r"(\d+)",
            None, 0, "{{{{Bug|{0}}}}}"),

        # official packages, with and without alternative text
        # FIXME: don't match pkgbase - see [[Firefox]]
        (r"https?\:\/\/(?:www\.)?archlinux\.org\/packages\/[\w-]+\/(?:any|i686|x86_64)\/([a-zA-Z0-9@._+-]+)\/?",
            "{0}", re.IGNORECASE, "{{{{Pkg|{0}}}}}"),
        (r"https?\:\/\/(?:www\.)?archlinux\.org\/packages\/[\w-]+\/(?:any|i686|x86_64)\/([a-zA-Z0-9@._+-]+)\/?",
            None, 0, "{{{{Pkg|{0}}}}}"),

        # AUR packages, with and without alternative text
        (r"https?\:\/\/aur\.archlinux\.org\/packages\/([a-zA-Z0-9@._+-]+)\/?",
            "{0}", re.IGNORECASE, "{{{{AUR|{0}}}}}"),
        (r"https?\:\/\/aur\.archlinux\.org\/packages\/([a-zA-Z0-9@._+-]+)\/?",
            None, 0, "{{{{AUR|{0}}}}}"),

        # Wikipedia interwiki
        (r"https?\:\/\/en\.wikipedia\.org\/wiki\/([^\]\?]+)",
            ".*", 0, "[[wikipedia:{0}|{1}]]"),
        (r"https?\:\/\/en\.wikipedia\.org\/wiki\/([^\]\?]+)",
            None, 0, "[[wikipedia:{0}]]"),
    ]

    # list of (edit_summary, url_regex, url_replacement) tuples, where:
    #   - edit_summary: a string with the edit summary to use for this replacement
    #   - url_regex: a regular expression matching the URL (using re.fullmatch)
    #   - url_replacement: a format string used as a replacement for the URL
    #                      (it is formatted using the groups matched by url_regex)
    #       The string can be in either of two formats:
    #       - as a native Python format string: matched groups are substituted for
    #         {0}, {1} and so on. See the format string syntax for details:
    #         https://docs.python.org/3/library/string.html#formatstrings
    #       - as a Jinja2 template: named groups are passed as variables, unnamed
    #         groups are in a special variable "m" and can be accessed as
    #         {{m[0]}}, {{m[1]}} and so on. See the template language documentation
    #         for details: https://jinja.palletsprojects.com/en/2.11.x/templates/
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
        ("update old mailman URLs from archlinux.org/mailman/listinfo/ to lists.archlinux.org/listinfo/",
            r"https?\:\/\/(?:www\.)?archlinux\.org\/mailman\/listinfo\/(?P<mailinglist>.+)?",
            "https://lists.archlinux.org/listinfo/{% if mailinglist is not none %}{{mailinglist}}{% endif %}"),
        ("update old mailman URLs from archlinux.org/pipermail/ to lists.archlinux.org/pipermail/",
            r"https?\:\/\/(?:www\.)?archlinux\.org\/pipermail\/(?P<mail>.+)?",
            "https://lists.archlinux.org/pipermail/{% if mail is not none %}{{mail}}{% endif %}"),

        # ancient php pages
        ("update ancient archweb URLs from archlinux.org/*.php to archlinux.org/*/",
            r"https?\:\/\/(?:www\.)?archlinux\.org\/(?P<page>.+?)\.php",
            "https://archlinux.org/{{page}}/"),

        # Archweb
        ("update archweb URLs from www.archlinux.org to archlinux.org",
            r"https?\:\/\/www\.archlinux\.org(?P<path>\/.*)?",
            "https://archlinux.org{% if path is not none %}{{path}}{% endif %}"),

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
        ("update old links to (projects|git).archlinux.org",
            r"https?\:\/\/(?:projects|git)\.archlinux\.org\/(?P<project>archiso|aurweb|infrastructure).git(?:\/(?P<type>commit|tree|plain|log))?(?P<path>[^?]+?)?(?:\?h=(?P<branch>[^&#?]+?))?(?:[&?]id=(?P<commit>[0-9A-Fa-f]+))?(?:#n(?P<linenum>\d+))?",
            "https://gitlab.archlinux.org/archlinux/{{project}}{% if type is not none %}/{{type | replace('plain', 'raw') | replace('log', 'commits')}}{% if commit is not none %}/{{commit}}{% elif branch is not none %}/{{branch}}{% elif path is not none %}/master{% endif %}{% if (path is not none) and (path != '/') %}{{path}}{% endif %}{% if linenum is not none %}#L{{linenum}}{% endif %}{% endif %}"),

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
            "https://www.kernel.org/doc/html/latest{{path}}{% if extension is not none %}.html{% endif %}"),

        # wireless.wiki.kernel.org
        ("update wireless.kernel.org links",
            r"https?\:\/\/wireless\.kernel\.org/(?P<path>[^#]*)(?P<fragment>#.+)?",
            "https://wireless.wiki.kernel.org/{{path}}{% if fragment is not none %}{{fragment | lower}}{% endif %}"),

        # Stack Exchange short links
        ("remove user IDs from short links to Stack Exchange posts",
            r"https?\:\/\/(?P<domain>(:?\w+\.)?stackexchange\.com|stackoverflow\.com|askubuntu\.com|serverfault\.com|superuser\.com|mathoverflow\.net)\/a\/(?P<answer>\d+)\/\d+",
            "https://{{domain}}/a/{{answer}}"),
        # TODO: use Special:Permalink on ArchWiki: https://wiki.archlinux.org/index.php?title=Pacman/Tips_and_tricks&diff=next&oldid=630006
    ]

    https_everywhere_rules_path = os.path.join(os.path.dirname(__file__), "https_everywhere/default.rulesets.json")

    def __init__(self, api, db, **kwargs):
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

        self.https_everywhere_rules = RuleTrie()
        data = json.load(open(self.https_everywhere_rules_path, "r"))
        for r in data:
            ruleset = Ruleset(r, "<unknown file>")
            if ruleset.defaultOff:
                logging.debug("Skipping HTTPS Everywhere rule '{}', reason: {}".format(ruleset.name, ruleset.defaultOff))
                continue
            self.https_everywhere_rules.addRuleset(ruleset)

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

    def check_extlink_to_wikilink(self, wikicode, extlink, url):
        match = self.wikisite_extlink_regex.fullmatch(url.url)
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

    def check_extlink_replacements(self, wikicode, extlink, url):
        for url_regex, text_cond, text_cond_flags, replacement in self.extlink_replacements:
            if (text_cond is None and extlink.title is not None) or (text_cond is not None and extlink.title is None):
                continue
            match = url_regex.fullmatch(url.url)
            if match:
                if extlink.title is None:
                    repl = replacement.format(*match.groups())
                    wikicode.replace(extlink, repl)
                    # TODO: make sure that the link is unflagged after replacement
                    return True
                else:
                    groups = [re.escape(g) for g in match.groups()]
                    alt_text = str(extlink.title).strip()
                    if re.fullmatch(text_cond.format(*groups), alt_text, text_cond_flags):
                        wikicode.replace(extlink, replacement.format(*match.groups(), extlink.title))
                        # TODO: make sure that the link is unflagged after replacement
                        return True
                    else:
                        logger.warning("external link that should be replaced, but has custom alternative text: {}".format(extlink))
        return False

    def check_url_replacements(self, wikicode, extlink, url):
        for edit_summary, url_regex, url_replacement in self.url_replacements:
            match = url_regex.fullmatch(url.url)
            if match:
                if "{0}" in url_replacement:
                    new_url = url_replacement.format(*match.groups())
                else:
                    env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True)
                    template = env.from_string(url_replacement)
                    new_url = template.render(m=match.groups(), **match.groupdict())

                # check if the resulting URL is valid
                if not self.check_url(new_url, allow_redirects=True):
                    logger.warning("URL not replaced: {}".format(url))
                    return False

                # post-processing for gitlab.archlinux.org links
                #   - gitlab uses "blob" for files and "tree" for directories
                #   - if "blob" or "tree" is used incorrectly, gitlab gives 302 to the correct one
                #     (so we should replace new_url with what gitlab gives us)
                #   - the "/-/" disambiguator (which is added by gitlab's redirects) is ugly and should be removed thereafter
                #   - gitlab gives 302 to the master branch instead of 404 for non-existent files/directories
                if new_url.startswith("https://gitlab.archlinux.org"):
                    # use same query as ExtlinkStatusChecker.check_url
                    response = self.session.get(new_url, headers=self.headers, timeout=self.timeout, stream=True, allow_redirects=True)
                    if len(response.history) > 0:
                        if response.url.endswith("/master"):
                            # this is gitlab's "404" in most cases
                            logger.warning("URL not replaced (Gitlab redirected to a master branch): {}".format(url))
                            return False
                        new_url = response.url
                    new_url = new_url.replace("/-/", "/", 1)

                # some patterns match even the target
                # (e.g. links on addons.mozilla.org which already do not have a language code)
                if url.url == new_url:
                    return False

                extlink.url = new_url
                ensure_unflagged_by_template(wikicode, extlink, "Dead link", match_only_prefix=True)
                return edit_summary
        return False

    def check_http_to_https(self, wikicode, extlink, url):
        if url.scheme != "http":
            return

        # check HSTS preload list first
        # (Chromium's static list of sites supporting HTTP Strict Transport Security)
        if in_hsts_preload(url.netloc.lower()):
            new_url = str(extlink.url).replace("http://", "https://", 1)
        # check HTTPS Everywhere rules next
        elif self.https_everywhere_rules.matchingRulesets(url.netloc.lower()):
            match = self.https_everywhere_rules.transformUrl(url)
            new_url = match.url
        else:
            return

        # there is no reason to update broken links
        if self.check_url(new_url):
            extlink.url = new_url
        else:
            logger.warning("broken URL not updated to https: {}".format(url))

    def update_extlink(self, wikicode, extlink, summary_parts):
        # prepare URL - fix parsing of adjacent templates, replace HTML entities, parse with urllib3
        url = self.prepare_url(wikicode, extlink)
        if url is None:
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
