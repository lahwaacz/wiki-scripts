#! /usr/bin/env python3

# FIXME: space-initialized code blocks should be skipped, but mwparserfromhell does not support that

# TODO:
#   detect self-redirects (definitely interactive only)
#   changes rejected interactively should be logged
#   warn if the link leads to an archived page

import difflib
import re
import logging
import contextlib
import datetime

import requests
import mwparserfromhell

from ws.client import API, APIError
from ws.db.database import Database
from ws.utils import LazyProperty
from ws.interactive import edit_interactive, require_login, InteractiveQuit
from ws.diff import diff_highlighted
import ws.ArchWiki.lang as lang
from ws.parser_helpers.encodings import dotencode, queryencode
from ws.parser_helpers.title import canonicalize, TitleError, InvalidTitleCharError
from ws.parser_helpers.wikicode import get_anchors, ensure_flagged_by_template, ensure_unflagged_by_template

logger = logging.getLogger(__name__)


def get_ranks(key, iterable):
    """
    Get a list of similarity ratios for a key in iterable.

    :param str key: the main key to compare
    :param iterable:
        an iterable containing secondary keys to compare against the main key
    :returns:
        a list of ``(item, ratio)`` tuples sorted by ``ratio`` in descending
        order, where ``item`` is an item from ``iterable`` and ``ratio`` its
        similarity ratio
    """
    sm = difflib.SequenceMatcher(a=key)
    ranks = []
    for item in iterable:
        sm.set_seq2(item)
        ratio = sm.ratio()
        ranks.append( (item, ratio) )
    ranks.sort(key=lambda match: match[1], reverse=True)
    return ranks


def get_edit_checker(wikicode, summary_parts):
    @contextlib.contextmanager
    def checker(summary):
        text = str(wikicode)
        try:
            yield
        finally:
            if text != str(wikicode):
                summary_parts.append(summary)
    return checker


class ExtlinkRules:

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
    replacements = [
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

        # change http:// to https:// for archlinux.org and wikipedia.org (do it at the bottom, i.e. with least priority)
        (r"http:\/\/((?:[a-z]+\.)?(?:archlinux|wikipedia)\.org(?:\/\S+)?\/?)",
            ".*", 0, "[https://{0} {1}]"),
        (r"http:\/\/((?:[a-z]+\.)?(?:archlinux|wikipedia)\.org(?:\/\S+)?\/?)",
            None, 0, "https://{0}"),
    ]

    def __init__(self):
        _replacements = []
        for url_regex, text_cond, text_cond_flags, replacement in self.replacements:
            compiled = re.compile(url_regex)
            _replacements.append( (compiled, text_cond, text_cond_flags, replacement) )
        self.replacements = _replacements

    @LazyProperty
    def extlink_regex(self):
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

    def extlink_to_wikilink(self, wikicode, extlink):
        match = self.extlink_regex.fullmatch(str(extlink.url))
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

    def extlink_replacements(self, wikicode, extlink):
        for url_regex, text_cond, text_cond_flags, replacement in self.replacements:
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

    def update_extlink(self, wikicode, extlink):
        # always make sure to return as soon as the extlink is invalidated
        self.strip_extra_brackets(wikicode, extlink)
        if self.extlink_to_wikilink(wikicode, extlink):
            return
        if self.extlink_replacements(wikicode, extlink):
            return

class WikilinkRules:
    """
    Assumptions:

    - all titles are case-insensitive on the first letter (true on ArchWiki)
    - alternative text is intentional, no replacements there
    """

    def __init__(self, api, db, *, interactive=False):
        self.api = api
        self.db = db
        self.interactive = interactive

        # mapping of canonical titles to displaytitles
        self.displaytitles = {}
        for ns in self.api.site.namespaces.keys():
            if ns < 0:
                continue
            for page in self.api.generator(generator="allpages", gaplimit="max", gapnamespace=ns, prop="info", inprop="displaytitle"):
                self.displaytitles[page["title"]] = page["displaytitle"]

        self.void_update_cache = set()

    def check_trivial(self, wikilink, title):
        """
        Perform trivial simplification, replace `[[Foo|foo]]` with `[[foo]]`.

        :param wikilink: instance of `mwparserfromhell.nodes.wikilink.Wikilink`
                         representing the link to be checked
        :param title: the parsed :py:attr:`wikilink.title`
        :type title: :py:class:`mw.parser_helpers.title.Title`
        """
        if wikilink.text is None:
            return

        try:
            text = self.api.Title(wikilink.text)
        except TitleError:
            return

        if title == text:
            # title is mandatory, so the text becomes the title
            wikilink.title = title.leading_colon + str(wikilink.text)
            wikilink.text = None

    def check_relative(self, src_title, wikilink, title):
        """
        Use relative links whenever possible. For example, links to sections such as
        `[[Foo#Bar]]` on a page `title` are replaced with `[[#Bar]]` whenever `Foo`
        redirects to or is equivalent to `title`.

        :param str src_title: the title of the page being checked
        :param wikilink: the link to be checked
        :type wikilink: :py:class:`mwparserfromhell.nodes.wikilink.Wikilink`
        :param title: the parsed :py:attr:`wikilink.title`
        :type title: :py:class:`mw.parser_helpers.title.Title`
        """
        if title.iwprefix or not title.sectionname:
            return
        # check if title is a redirect
        target = self.api.redirects.map.get(title.fullpagename)
        if target:
            _title = self.api.Title(target)
            _title.sectionname = title.sectionname
        else:
            _title = title

        if canonicalize(src_title) == _title.fullpagename:
            wikilink.title = "#" + _title.sectionname
            title.parse(wikilink.title)

    def check_redirect_exact(self, src_title, wikilink, title):
        """
        Replace `[[foo|bar]]` with `[[bar]]` if `foo` and `bar` point to the
        same page after resolving redirects.

        :param str src_title: the title of the page being checked
        :param wikilink: the link to be checked
        :type wikilink: :py:class:`mwparserfromhell.nodes.wikilink.Wikilink`
        :param title: the parsed :py:attr:`wikilink.title`
        :type title: :py:class:`mw.parser_helpers.title.Title`
        """
        if wikilink.text is None:
            return

        try:
            text = self.api.Title(wikilink.text)
        except TitleError:
            return

        # skip links to sections ([[#Foo|Foo]] should remain even if `Foo` redirects to `This page#Foo`)
        if not title.pagename:
            return

        # handle relative links properly
        # (we assume that subpages are enabled for all namespaces)
        title = title.make_absolute(src_title)

        target1 = self.api.redirects.map.get(title.fullpagename)
        target2 = self.api.redirects.map.get(text.fullpagename)
        if target1 is not None:
            target1 = self.api.Title(target1)
            # bail out if we lost the fragment
            if target1.sectionname != title.sectionname:
                return
        if target2 is not None:
            target2 = self.api.Title(target2)

        if target1 is not None and target2 is not None:
            if target1 == target2:
                wikilink.title = wikilink.text
                wikilink.text = None
                title.parse(wikilink.title)
        elif target1 is not None:
            if target1 == text:
                wikilink.title = wikilink.text
                wikilink.text = None
                title.parse(wikilink.title)
        elif target2 is not None:
            if target2 == title:
                wikilink.title = wikilink.text
                wikilink.text = None
                title.parse(wikilink.title)

    def check_redirect_capitalization(self, wikilink, title):
        """
        Avoid redirect iff the difference is only in capitalization.

        :param wikilink: the link to be checked
        :type wikilink: :py:class:`mwparserfromhell.nodes.wikilink.Wikilink`
        :param title: the parsed :py:attr:`wikilink.title`
        :type title: :py:class:`mw.parser_helpers.title.Title`
        """
        # run only in interactive mode
        if self.interactive is False:
            return

        # FIXME: very common false positive
        if title.pagename.lower().startswith("wpa supplicant"):
            return

        # might be only a section, e.g. [[#foo]]
        if title.fullpagename:
            target = self.api.redirects.map.get(title.fullpagename)
            if target is not None and target.lower() == title.fullpagename.lower():
                if title.sectionname:
                    target += "#" + title.sectionname
                wikilink.title = target
                title.parse(wikilink.title)

    def check_displaytitle(self, wikilink, title):
        # Replacing underscores and capitalization as per DISPLAYTITLE attribute
        # is not safe (e.g. 'wpa_supplicant' and 'WPA supplicant' are equivalent
        # without deeper context), so do it only in interactive mode.
        if self.interactive is False:
            return
        # Avoid largescale edits if there is an alternative text.
        if wikilink.text is not None:
            return
        # we can't check interwiki links
        if title.iwprefix:
            return
        # skip relative links
        if not title.fullpagename or title.fullpagename.startswith("/"):
            return
        # skip links to special namespaces
        if title.namespacenumber < 0:
            return
        # report pages without DISPLAYTITLE (red links)
        if title.fullpagename not in self.displaytitles:
            logger.warning("wikilink to non-existing page: {}".format(wikilink))
            return

        # FIXME: very common false positive
        if title.pagename == "Wpa supplicant":
            return

        # assemble new title
        # TODO: simplify (see #25)
        new = self.displaytitles[title.fullpagename]
        if title.sectionname:
            # preserve original section anchor, it will be checked in self.check_anchor()
            _, anchor = wikilink.title.split("#", maxsplit=1)
            new += "#" + anchor

        # TODO: the following code block would strip the leading colon
        if title.leading_colon:
            return

        # skip if only the case of the first letter is different
        if wikilink.title[1:] != new[1:]:
            first_letter = wikilink.title[0]
            wikilink.title = new
            # preserve the case of the first letter if the rest differs only in spaces/underscores
            # (e.g. don't replace [[environment_variables]] with [[Environment variables]])
            if wikilink.title[1:].replace(" ", "_") == new[1:].replace(" ", "_"):
                wikilink.title = first_letter + wikilink.title[1:]
            title.parse(wikilink.title)

    def check_anchor(self, src_title, wikilink, title):
        """
        :returns:
            ``True`` if the anchor is correct or has been corrected, ``False``
            if it is definitely broken, ``None`` if it can't be checked at all
            or the check was indecisive and a warning/error has been printed to
            the log.
        """
        # TODO: beware of https://phabricator.wikimedia.org/T20431

        # we can't check interwiki links
        if title.iwprefix:
            return None

        # empty sectionname is always valid
        if title.sectionname == "":
            return None

        # determine target page
        _target_title = title.make_absolute(src_title)

        # skip links to special pages (e.g. [[Special:Preferences#mw-prefsection-rc]])
        if _target_title.namespacenumber < 0:
            return None

        # resolve redirects
        anchor_on_redirect_to_section = False
        if _target_title.fullpagename in self.api.redirects.map:
            _target_title = self.api.Title(self.api.redirects.resolve(_target_title.fullpagename))
            if _target_title.sectionname:
                logger.warning("warning: section fragment placed on a redirect to possibly different section: {}".format(wikilink))
                anchor_on_redirect_to_section = True

        # get lists of section headings and anchors
        _result = self.db.query(titles=_target_title.fullpagename, prop="sections", secprop={"title", "anchor"})
        _result = list(_result)
        assert len(_result) == 1
        if "missing" in _result[0]:
            logger.error("could not find content of page: '{}' (wikilink {})".format(_target_title.fullpagename, wikilink))
            return None
        headings = [section["title"] for section in _result[0].get("sections", [])]
        anchors = [section["anchor"] for section in _result[0].get("sections", [])]

        if len(headings) == 0:
            logger.warning("wikilink with broken section fragment: {}".format(wikilink))
            return False

        anchor = dotencode(title.sectionname)
        needs_fix = True

        # handle double-anchor redirects first
        if anchor_on_redirect_to_section is True:
            if anchor in anchors:
                return True
            else:
                return False

        # try exact match first
        if anchor in anchors:
            needs_fix = False
        # otherwise try case-insensitive match to detect differences in capitalization
        elif self.interactive is True:
            # FIXME: first detect section renaming properly, fuzzy search should be only the last resort to deal with typos and such
            ranks = get_ranks(anchor, anchors)
            ranks = list(filter(lambda rank: rank[1] >= 0.8, ranks))
            if len(ranks) == 1 or ( len(ranks) >= 2 and ranks[0][1] - ranks[1][1] > 0.2 ):
                logger.debug("wikilink {}: replacing anchor '{}' with '{}' on similarity level {}".format(wikilink, anchor, ranks[0][0], ranks[0][1]))
                anchor = ranks[0][0]
            elif len(ranks) > 1:
                logger.debug("skipping {}: multiple feasible anchors per similarity ratio: {}".format(wikilink, ranks))
                return False
            else:
                logger.warning("wikilink with broken section fragment: {}".format(wikilink))
                return False
        else:
            logger.warning("wikilink with broken section fragment: {}".format(wikilink))
            return False

        # assemble new section fragment
        # try to preserve the character separating base anchor and numeric suffix
        dupl_match = re.match("(.+)([_ ])(\d+)$", str(wikilink.title))
        if dupl_match:
            suffix_sep = dupl_match.group(2)
        else:
            suffix_sep = " "
        # get_anchors makes sure to strip markup and handle duplicate section names
        new_fragment = get_anchors(headings, pretty=True, suffix_sep=suffix_sep)[anchors.index(anchor)]

        # Avoid beautification if there is alternative text and the link
        # actually works.
        if wikilink.text is None or needs_fix is True:
            # preserve title set in check_displaytitle()
            # TODO: simplify (see #25)
            t, _ = wikilink.title.split("#", maxsplit=1)
            wikilink.title = t + "#" + new_fragment
            title.parse(wikilink.title)

        return True

    def collapse_whitespace_pipe(self, wikilink):
        """
        Strip whitespace around the pipe in wikilinks.

        :param wikilink: instance of `mwparserfromhell.nodes.wikilink.Wikilink`
                         representing the link to be checked
        """
        if wikilink.text is not None:
            wikilink.title = wikilink.title.rstrip()
            wikilink.text = wikilink.text.lstrip()

    def collapse_whitespace(self, wikicode, wikilink):
        """
        Attempt to fix spacing around wiki links after the substitutions.

        :param wikicode: instance of `mwparserfromhell.wikicode.Wikicode`
                         containing the wikilink
        :param wikilink: instance of `mwparserfromhell.nodes.wikilink.Wikilink`
                         representing the link to be checked
        """
        parent, _ = wikicode._do_strong_search(wikilink, True)
        index = parent.index(wikilink)

        def _get_text(index):
            try:
                node = parent.get(index)
                if not isinstance(node, mwparserfromhell.nodes.text.Text):
                    return None
                return node
            except IndexError:
                return None

        prev = _get_text(index - 1)
        next_ = _get_text(index)

        if prev is not None and (prev.endswith(" ") or prev.endswith("\n")):
            wikilink.title = wikilink.title.lstrip()
        if next_ is not None and (next_.startswith(" ") or next_.endswith("\n")):
            if wikilink.text is not None:
                wikilink.text = wikilink.text.rstrip()
            else:
                wikilink.title = wikilink.title.rstrip()

    def update_wikilink(self, wikicode, wikilink, src_title, summary_parts):
        if str(wikilink) in self.void_update_cache:
            logger.debug("Skipping wikilink {} due to void-update cache.".format(wikilink))
            return

        title = self.api.Title(wikilink.title)
        # skip interlanguage links (handled by interlanguage.py)
        if title.iwprefix in self.api.site.interlanguagemap.keys():
            return

        summary = get_edit_checker(wikicode, summary_parts)

        with summary("simplification and beautification of wikilinks"):
            # beautify if urldecoded
            # FIXME: make it implicit - it does not always propagate from the Title class
            if not title.iwprefix and re.search("%[0-9a-f]{2}", str(wikilink.title), re.IGNORECASE):
                # handle links with leading colon properly
                wikilink.title = title.leading_colon + str(title)
                # FIXME: should be done in the Title class
                # the anchor is dot-encoded, but percent-encoding wors for links too
                # and is even rendered nicely
                wikilink.title = str(wikilink.title).replace("[", "%5B").replace("|", "%7C").replace("]", "%5D")

            self.collapse_whitespace_pipe(wikilink)
            self.check_trivial(wikilink, title)
            self.check_relative(src_title, wikilink, title)
            if lang.detect_language(src_title)[1] == "English":
                self.check_redirect_exact(src_title, wikilink, title)
            self.check_redirect_capitalization(wikilink, title)

            # reparse the title, the redirect checks might change it non-equivalently
            title = self.api.Title(wikilink.title)

            self.check_displaytitle(wikilink, title)

        with summary("fixed section fragments"):
            anchor_result = self.check_anchor(src_title, wikilink, title)
        if anchor_result is False:
            with summary("flagged broken section links"):
                ensure_flagged_by_template(wikicode, wikilink, "Broken section link")
        else:
            with summary("unflagged working section links"):
                ensure_unflagged_by_template(wikicode, wikilink, "Broken section link")

        with summary("simplification and beautification of wikilinks"):
            # partial second pass
            self.check_trivial(wikilink, title)
            if lang.detect_language(src_title)[1] == "English":
                self.check_redirect_exact(src_title, wikilink, title)

            # collapse whitespace around the link, e.g. 'foo [[ bar]]' -> 'foo [[bar]]'
            self.collapse_whitespace(wikicode, wikilink)

        # cache context-less, correct wikilinks that don't need any update
        if title.pagename and len(summary_parts) == 0 and anchor_result is True:
            self.void_update_cache.add(str(wikilink))


class ManTemplateRules:
    url_prefix = "http://jlk.fjfi.cvut.cz/arch/manpages/man/"

    def __init__(self, timeout, max_retries):
        self.timeout = timeout
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(max_retries=max_retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self.cache_valid_urls = set()
        self.cache_invalid_urls = set()

    def update_man_template(self, wikicode, template):
        if template.name.lower() != "man":
            return

        now = datetime.datetime.utcnow()
        deadlink_params = [now.year, now.month, now.day]
        deadlink_params = ["{:02d}".format(i) for i in deadlink_params]

        if not template.has(1) or not template.has(2, ignore_empty=True):
            ensure_flagged_by_template(wikicode, template, "Dead link", *deadlink_params, overwrite_parameters=False)
            return

        url = self.url_prefix
        if template.has("pkg"):
            url += template.get("pkg").value.strip() + "/"
        url += queryencode(template.get(2).value.strip())
        if template.get(1).value.strip():
            url += "." + template.get(1).value.strip()
        if template.has(3):
            url += "#{}".format(queryencode(template.get(3).value.strip()))

        if template.has("url"):
            explicit_url = template.get("url").value.strip()
        else:
            explicit_url = None

        def check_url(url):
            if url.startswith("ftp://"):
                logger.error("The FTP protocol is not supported by the requests module. URL: {}".format(url))
                return True
            if url in self.cache_valid_urls:
                return True
            elif url in self.cache_invalid_urls:
                return False
            response = self.session.get(url, timeout=self.timeout)
            if response.status_code == 200:
                # heuristics to get the missing section (redirect from some_page to some_page.1)
                # WARNING: if the manual exists in multiple sections, the first one might not be the best
                if len(response.history) == 1 and response.url.startswith(url + "."):
                    # template parameter 1= should be empty
                    assert not template.has(1, ignore_empty=True)
                    template.add(1, response.url[len(url) + 1:])
                    self.cache_valid_urls.add(response.url)
                    return True
                else:
                    self.cache_valid_urls.add(url)
                    return True
            elif response.status_code >= 400:
                self.cache_invalid_urls.add(url)
                return False
            else:
                raise NotImplementedError("Unexpected status code {} for man page URL: {}".format(response.status_code, url))

        # check if the template parameters form a valid URL
        if check_url(url):
            ensure_unflagged_by_template(wikicode, template, "Dead link")
            # remove explicit url= parameter - not necessary
            if explicit_url is not None:
                template.remove("url")
        elif explicit_url is None:
            ensure_flagged_by_template(wikicode, template, "Dead link", *deadlink_params, overwrite_parameters=False)
        elif explicit_url != "":
            if check_url(explicit_url):
                ensure_unflagged_by_template(wikicode, template, "Dead link")
            else:
                ensure_flagged_by_template(wikicode, template, "Dead link", *deadlink_params, overwrite_parameters=False)


class LinkChecker(ExtlinkRules, WikilinkRules, ManTemplateRules):

    interactive_only_pages = ["ArchWiki:Sandbox"]
    skip_pages = ["Table of contents", "Help:Editing", "ArchWiki:Reports", "ArchWiki:Requests", "ArchWiki:Statistics"]
    # article status templates, lowercase
    skip_templates = ["accuracy", "archive", "bad translation", "expansion", "laptop style", "merge", "move", "out of date", "remove", "stub", "style", "translateme"]

    def __init__(self, api, db, interactive=False, dry_run=False, first=None, title=None, langnames=None, connection_timeout=30, max_retries=3):
        if not dry_run:
            # ensure that we are authenticated
            require_login(api)

        # init inherited
        ExtlinkRules.__init__(self)
        WikilinkRules.__init__(self, api, db, interactive=interactive)
        ManTemplateRules.__init__(self, connection_timeout, max_retries)

        self.api = api
        self.db = db
        self.interactive = interactive
        self.dry_run = dry_run

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
        group.add_argument("-i", "--interactive", action="store_true",
                help="enables interactive mode")
        group.add_argument("--dry-run", action="store_true",
                help="enables dry-run mode (changes are only shown and discarded)")
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
        return klass(api, db, interactive=args.interactive, dry_run=args.dry_run, first=args.first, title=args.title, langnames=langnames, connection_timeout=args.connection_timeout, max_retries=args.connection_max_retries)

    def update_page(self, src_title, text):
        """
        Parse the content of the page and call various methods to update the links.

        :param str src_title: title of the page
        :param str text: content of the page
        :returns: a (text, edit_summary) tuple, where text is the updated content
            and edit_summary is the description of performed changes
        """
        if lang.detect_language(src_title)[0] in self.interactive_only_pages and self.interactive is False:
            logger.info("Skipping page [[{}]] which is blacklisted for non-interactive mode".format(src_title))
            return text, ""

        logger.info("Parsing page [[{}]] ...".format(src_title))
        # FIXME: skip_style_tags=True is a partial workaround for https://github.com/earwig/mwparserfromhell/issues/40
        wikicode = mwparserfromhell.parse(text, skip_style_tags=True)
        summary_parts = []

        summary = get_edit_checker(wikicode, summary_parts)

        for extlink in wikicode.ifilter_external_links(recursive=True):
            # skip links inside article status templates
            parent = wikicode.get(wikicode.index(extlink, recursive=True))
            if isinstance(parent, mwparserfromhell.nodes.template.Template) and parent.name.lower() in self.skip_templates:
                continue
            with summary("replaced external links"):
                self.update_extlink(wikicode, extlink)

        for wikilink in wikicode.ifilter_wikilinks(recursive=True):
            # skip links inside article status templates
            parent = wikicode.get(wikicode.index(wikilink, recursive=True))
            if isinstance(parent, mwparserfromhell.nodes.template.Template) and parent.name.lower() in self.skip_templates:
                continue
            try:
                self.update_wikilink(wikicode, wikilink, src_title, summary_parts)
            # this can happen, e.g. due to [[{{TALKPAGENAME}}]]
            except InvalidTitleCharError:
                pass

        for template in wikicode.ifilter_templates(recursive=True):
            # skip templates that may be added or removed
            if str(template.name) in {"Broken section link", "Dead link"}:
                continue
            # skip links inside article status templates
            parent = wikicode.get(wikicode.index(template, recursive=True))
            if isinstance(parent, mwparserfromhell.nodes.template.Template) and parent.name.lower() in self.skip_templates:
                continue
            _pure_template = lang.detect_language(str(template.name))[0]
            if _pure_template.lower() in {"related", "related2"}:
                target = template.get(1).value
                # temporarily convert the {{Related}} to wikilink to reuse the update code
                wl = mwparserfromhell.nodes.wikilink.Wikilink(target)
                wikicode.replace(template, wl)
                # update
                try:
                    self.update_wikilink(wikicode, wl, src_title, summary_parts)
                # this can happen, e.g. due to [[{{TALKPAGENAME}}]]
                except InvalidTitleCharError:
                    continue
                # replace back
                target.value = str(wl.title)
                wikicode.replace(wl, template)
            elif template.name.lower() == "man":
                with summary("updated man page links"):
                    self.update_man_template(wikicode, template)

        # deduplicate and keep order
        parts = set()
        parts_add = parts.add
        summary_parts = [part for part in summary_parts if not (part in parts or parts_add(part))]

        edit_summary = ", ".join(summary_parts)
        if self.interactive is True:
            edit_summary += " (interactive)"

        return str(wikicode), edit_summary

    def _edit(self, title, pageid, text_new, text_old, timestamp, edit_summary):
        if text_old != text_new:
            if self.dry_run:
                diff = diff_highlighted(text_old, text_new, title + ".old", title + ".new", timestamp, "<utcnow>")
                print(diff)
                print("Edit summary:  " + edit_summary)
                print("(edit discarded due to --dry-run)")
            else:
                try:
                    if self.interactive is False:
                        self.api.edit(title, pageid, text_new, timestamp, edit_summary, bot="")
                    else:
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
        namespaces = [0, 4, 14]
        if self.interactive is True:
            namespaces.append(12)

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

    checker = ws.config.object_from_argparser(LinkChecker, description="Parse all pages on the wiki and try to fix/simplify/beautify links")

    try:
        checker.run()
    except (InteractiveQuit, KeyboardInterrupt):
        pass
