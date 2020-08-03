#! /usr/bin/env python3

import re
import logging

import mwparserfromhell
import jinja2

from .CheckerBase import get_edit_summary_tracker
from .ExtlinkStatusChecker import ExtlinkStatusChecker
from ws.utils import LazyProperty

__all__ = ["ExtlinkReplacements"]

logger = logging.getLogger(__name__)

class ExtlinkReplacements(ExtlinkStatusChecker):

    retype = type(re.compile(""))
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
        (re.escape("https://bugs.archlinux.org/task/") + "(\d+)",
            "(FS|flyspray) *#?{0}", 0, "{{{{Bug|{0}}}}}"),

        # official packages, with and without alternative text
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

    # list of (url_regex, url_replacement) tuples, where:
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
        # change http:// to https:// for archlinux.org and wikipedia.org (do it at the bottom, i.e. with least priority)
#        (r"http:\/\/((?:[a-z]+\.)?(?:archlinux|wikipedia)\.org(?:\/\S+)?\/?)",
#          "https://{0}"),

        # migration of Arch's git URLs

        # svntogit commits
        (r"https?\:\/\/(?:projects|git)\.archlinux\.org\/svntogit\/(?P<repo>packages|community)\.git\/commit\/(?P<path>[^?]+?)?(?:\?h=[^&#?]+?)?(?:[&?]id=(?P<commit>[0-9A-Fa-f]+))",
          "https://github.com/archlinux/svntogit-{{repo}}/commit/{{commit}}{% if (path is not none) and ('/' in path) %}/{{path}}{% endif %}"),
        # svntogit blobs, raws and logs
        (r"https?\:\/\/(?:projects|git)\.archlinux\.org\/svntogit\/(?P<repo>packages|community)\.git\/(?P<type>tree|plain|log)\/(?P<path>[^?]+?)(?:\?h=(?P<branch>[^&#?]+?))?(?:[&?]id=(?P<commit>[0-9A-Fa-f]+))?(?:#n(?P<linenum>\d+))?",
          "https://github.com/archlinux/svntogit-{{repo}}/{{type | replace('tree', 'blob') | replace('plain', 'raw') | replace('log', 'commits')}}/{% if commit is not none %}{{commit}}/{% elif branch is not none %}{{branch}}/{% elif (path is not none) and (not path.startswith('packages')) %}packages/{% endif %}{{path}}{% if linenum is not none %}#L{{linenum}}{% endif %}"),
        # svntogit repos
        (r"https?\:\/\/(?:projects|git)\.archlinux\.org\/svntogit\/(?P<repo>packages|community)\.git(\/tree)?\/?",
          "https://github.com/archlinux/svntogit-{{repo}}"),

        # other git repos
        (r"https?\:\/\/(?:projects|git)\.archlinux\.org\/(?P<project>archiso|aurweb|infrastructure).git(?:\/(?P<type>commit|tree|plain|log))?(?P<path>[^?]+?)?(?:\?h=(?P<branch>[^&#?]+?))?(?:[&?]id=(?P<commit>[0-9A-Fa-f]+))?(?:#n(?P<linenum>\d+))?",
          "https://gitlab.archlinux.org/archlinux/{{project}}{% if type is not none %}/{{type | replace('plain', 'raw') | replace('log', 'commits')}}{% if commit is not none %}/{{commit}}{% elif branch is not none %}/{{branch}}{% elif path is not none %}/master{% endif %}{% if (path is not none) and (path != '/') %}{{path}}{% endif %}{% if linenum is not none %}#L{{linenum}}{% endif %}{% endif %}"),
    ]

    def __init__(self, api, db, **kwargs):
        super().__init__(api, db, **kwargs)

        _extlink_replacements = []
        for url_regex, text_cond, text_cond_flags, replacement in self.extlink_replacements:
            compiled = re.compile(url_regex)
            _extlink_replacements.append( (compiled, text_cond, text_cond_flags, replacement) )
        self.extlink_replacements = _extlink_replacements

        _url_replacements = []
        for url_regex, url_replacement in self.url_replacements:
            compiled = re.compile(url_regex)
            _url_replacements.append( (compiled, url_replacement) )
        self.url_replacements = _url_replacements

    @LazyProperty
    def wikisite_extlink_regex(self):
        general = self.api.site.general
        regex = re.escape(general["server"] + general["articlepath"].split("$1")[0])
        regex += "(?P<pagename>[^\s\?]+)"
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

    def check_extlink_to_wikilink(self, wikicode, extlink):
        match = self.wikisite_extlink_regex.fullmatch(str(extlink.url))
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
            return True
        return False

    def check_extlink_replacements(self, wikicode, extlink):
        for url_regex, text_cond, text_cond_flags, replacement in self.extlink_replacements:
            if (text_cond is None and extlink.title is not None) or (text_cond is not None and extlink.title is None):
                continue
            match = url_regex.fullmatch(str(extlink.url))
            if match:
                if extlink.title is None:
                    repl = replacement.format(*match.groups())
                    # FIXME: hack to preserve brackets (e.g. [http://example.com/] )
                    if extlink.brackets and not repl.startswith("[") and not repl.endswith("]"):
                        repl = "[{}]".format(repl)
                    wikicode.replace(extlink, repl)
                    return True
                else:
                    groups = [re.escape(g) for g in match.groups()]
                    alt_text = str(extlink.title).strip()
                    if re.fullmatch(text_cond.format(*groups), alt_text, text_cond_flags):
                        wikicode.replace(extlink, replacement.format(*match.groups(), extlink.title))
                        return True
                    else:
                        logger.warning("external link that should be replaced, but has custom alternative text: {}".format(extlink))
        return False

    def check_url_replacements(self, wikicode, extlink):
        for url_regex, url_replacement in self.url_replacements:
            match = url_regex.fullmatch(str(extlink.url))
            if match:
                if "{0}" in url_replacement:
                    new_url = url_replacement.format(*match.groups())
                else:
                    env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True)
                    template = env.from_string(url_replacement)
                    new_url = template.render(m=match.groups(), **match.groupdict())
                # check if the resulting URL is valid
                status = self.check_url(new_url, allow_redirects=False)
                if status is True:
                    extlink.url = new_url
                else:
                    logger.error("Link not replaced: {}".format(extlink))
                return True
        return False

    def update_extlink(self, wikicode, extlink, summary_parts):
        summary = get_edit_summary_tracker(wikicode, summary_parts)

        with summary("removed extra brackets"):
            self.strip_extra_brackets(wikicode, extlink)

        # create copy to avoid changing links that don't match
        if extlink.title is not None:
            extlink_copy = mwparserfromhell.nodes.ExternalLink(str(extlink.url), str(extlink.title), extlink.brackets, extlink.suppress_space)
        else:
            extlink_copy = mwparserfromhell.nodes.ExternalLink(str(extlink.url), extlink.title, extlink.brackets, extlink.suppress_space)

        # replace HTML entities like "&#61" or "&Sigma;" in the URL with their unicode equivalents
        # TODO: this may break templates if the decoded "&#61" stays in the replaced URL
        for entity in extlink.url.ifilter_html_entities(recursive=True):
            extlink.url.replace(entity, entity.normalize())

        # always make sure to return as soon as the extlink is matched and replaced
        with summary("replaced external links"):
            if self.check_extlink_to_wikilink(wikicode, extlink):
                return
            if self.check_extlink_replacements(wikicode, extlink):
                return
        # TODO: update this when more URLs are being updated
        with summary("update URLs from (projects|git).archlinux.org to github.com"):
            if self.check_url_replacements(wikicode, extlink):
                return

        # roll back the replacement of HTML entities if the extlink was not replaced by the rules
        wikicode.replace(extlink, extlink_copy)
