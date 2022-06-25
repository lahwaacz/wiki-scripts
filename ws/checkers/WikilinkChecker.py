#! /usr/bin/env python3

# TODO:
#   detect self-redirects (definitely interactive only)
#   warn if the link leads to an archived page

import difflib
import logging
import re

import mwparserfromhell

from .CheckerBase import get_edit_summary_tracker, CheckerBase
import ws.ArchWiki.lang as lang
from ws.parser_helpers.encodings import dotencode
from ws.parser_helpers.title import canonicalize, TitleError, InvalidTitleCharError
from ws.parser_helpers.wikicode import get_anchors, ensure_flagged_by_template, ensure_unflagged_by_template, is_flagged_by_template
from ws.db.selects.interwiki_redirects import get_interwiki_redirects

__all__ = ["WikilinkChecker"]

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


class WikilinkChecker(CheckerBase):
    """
    Assumptions:

    - all titles are case-insensitive on the first letter (true on ArchWiki)
    - alternative text is intentional, no replacements there
    """

    # article status templates, lowercase
    skip_templates = ["accuracy", "archive", "bad translation", "expansion", "laptop style", "merge", "move", "out of date", "remove", "stub", "style", "translateme"]

    def __init__(self, api, db, **kwargs):
        super().__init__(api, db, **kwargs)

        # mapping of canonical titles to displaytitles
        self.displaytitles = {}
        for ns in self.api.site.namespaces.keys():
            if ns < 0:
                continue
            for page in self.api.generator(generator="allpages", gaplimit="max", gapnamespace=ns, prop="info", inprop="displaytitle"):
                self.displaytitles[page["title"]] = page["displaytitle"]

        # mapping of interwiki redirects (the API does not have a query for this)
        self.interwiki_redirects = get_interwiki_redirects(self.db)

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

        # might be only a section, e.g. [[#foo]]
        if not title.fullpagename:
            return

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
            # if the displaytitle has first letter lowercase, it is used
            # (e.g. from [[Template:Lowercase title]])
            if not new[0].islower():
                # otherwise preserve the case of the first letter if the rest
                # differs only in spaces/underscores (e.g. don't replace
                # [[environment_variables]] with [[Environment variables]])
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

        # we can't check interwiki links
        if _target_title.fullpagename in self.interwiki_redirects:
            return None

        # skip links to special pages (e.g. [[Special:Preferences#mw-prefsection-rc]])
        if _target_title.namespacenumber < 0:
            return None

        # resolve redirects
        anchor_on_redirect_to_section = False
        if _target_title.fullpagename in self.api.redirects.map:
            _target_title = self.api.Title(self.api.redirects.resolve(_target_title.fullpagename))
            # check double-anchor redirects
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

        # handle double-anchor redirects first
        if anchor_on_redirect_to_section is True:
            if anchor in anchors:
                return True
            else:
                return False

        # try exact match first
        if anchor in anchors:
            pass
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
            # FIXME: anchors with encoded characters like '[' or ']' are not handled properly in non-interactive mode - links get flagged as broken, although they work
            # (e.g. [[Systemd-networkd#%5BNetDev%5D section|systemd-networkd]] - linked from [[systemd-timesyncd]])
            logger.warning("wikilink with broken section fragment: {}".format(wikilink))
            return False

        # assemble new section fragment
        # try to preserve the character separating base anchor and numeric suffix
        dupl_match = re.match(r"(.+)([_ ])(\d+)$", str(wikilink.title))
        if dupl_match:
            suffix_sep = dupl_match.group(2)
        else:
            suffix_sep = " "
        # get_anchors makes sure to strip markup and handle duplicate section names
        new_fragment = get_anchors(headings, pretty=True, suffix_sep=suffix_sep)[anchors.index(anchor)]

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
        src_lang = lang.detect_language(src_title)[1]

        title = self.api.Title(wikilink.title)
        # skip interlanguage links (handled by interlanguage.py)
        if title.iwprefix in self.api.site.interlanguagemap.keys():
            return

        summary = get_edit_summary_tracker(wikicode, summary_parts)

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
            if src_lang == "English":
                self.check_redirect_exact(src_title, wikilink, title)
            self.check_redirect_capitalization(wikilink, title)

            # reparse the title, the redirect checks might change it non-equivalently
            title = self.api.Title(wikilink.title)

            self.check_displaytitle(wikilink, title)

        with summary("fixed section fragments"):
            anchor_result = self.check_anchor(src_title, wikilink, title)
        if anchor_result is False:
            # links to archive should not be flagged by "Broken section link" ("Archived page" has higher priority)
            if not is_flagged_by_template(wikicode, wikilink, "Archived page", match_only_prefix=True):
                with summary("flagged broken section links"):
                    # first unflag to remove any translated version of the flag
                    ensure_unflagged_by_template(wikicode, wikilink, "Broken section link", match_only_prefix=True)
                    # flag with the correct translated template
                    flag = self.get_localized_template("Broken section link", src_lang)
                    ensure_flagged_by_template(wikicode, wikilink, flag)
        else:
            with summary("unflagged working section links"):
                ensure_unflagged_by_template(wikicode, wikilink, "Broken section link", match_only_prefix=True)

        with summary("simplification and beautification of wikilinks"):
            # partial second pass
            self.check_trivial(wikilink, title)
            if src_lang == "English":
                self.check_redirect_exact(src_title, wikilink, title)

            # collapse whitespace around the link, e.g. 'foo [[ bar]]' -> 'foo [[bar]]'
            self.collapse_whitespace(wikicode, wikilink)

        # cache context-less, correct wikilinks that don't need any update
        if title.pagename and len(summary_parts) == 0 and anchor_result is True:
            self.void_update_cache.add(str(wikilink))

    def handle_node(self, src_title, wikicode, node, summary_parts):
        # skip links inside article status templates
        parent = wikicode.get(wikicode.index(node, recursive=True))
        if isinstance(parent, mwparserfromhell.nodes.template.Template) and parent.name.lower() in self.skip_templates:
            return

        if isinstance(node, mwparserfromhell.nodes.Wikilink):
            try:
                self.update_wikilink(wikicode, node, src_title, summary_parts)
            # this can happen, e.g. due to [[{{TALKPAGENAME}}]]
            except InvalidTitleCharError:
                pass
        elif isinstance(node, mwparserfromhell.nodes.Template):
            _pure_template = lang.detect_language(str(node.name))[0]
            if _pure_template.lower() in {"related", "related2"}:
                target = node.get(1).value
                # temporarily convert the {{Related}} to wikilink to reuse the update code
                wl = mwparserfromhell.nodes.wikilink.Wikilink(target)
                wikicode.replace(node, wl)
                # update
                try:
                    self.update_wikilink(wikicode, wl, src_title, summary_parts)
                # this can happen, e.g. due to [[{{TALKPAGENAME}}]]
                except InvalidTitleCharError:
                    return
                # replace back
                target.value = str(wl.title)
                wikicode.replace(wl, node)
