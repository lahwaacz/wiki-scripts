#! /usr/bin/env python3

# FIXME:
#   handle :Category and Category links properly
#   how hard is skipping code blocks?

# TODO:
#   extlink -> wikilink conversion should be done first
#   skip category links, article status templates
#   detect self-redirects (definitely interactive only)

import difflib
import re
import logging

import mwparserfromhell

from ws.core import API, APIError
import ws.cache
import ws.utils
from ws.interactive import *
import ws.ArchWiki.lang as lang
from ws.parser_helpers.encodings import dotencode
from ws.parser_helpers.title import canonicalize, Title
from ws.parser_helpers.wikicode import get_section_headings, get_anchors

logger = logging.getLogger(__name__)


def get_ranks(key, iterable):
    """
    Get a list of similarity ratios for a key in iterable.

    :param str key: the main key to compare
    :param iterable:
        an iterable containing secondary keys to compare against the main key
    :returns: a list of ``(item, ratio)`` tuples, where ``item`` is an item from
        ``iterable`` and ``ratio`` its similarity ratio
    """
    sm = difflib.SequenceMatcher(a=key)
    ranks = []
    for item in iterable:
        sm.set_seq2(item)
        ratio = sm.ratio()
        ranks.append( (item, ratio) )
    ranks.sort(key=lambda match: match[1], reverse=True)
    return ranks

def strip_markup(text):
    wikicode = mwparserfromhell.parse(text)
    return wikicode.strip_code()


class LinkChecker:
    """
    Assumptions:

    - all titles are case-insensitive on the first letter (true on ArchWiki)
    - alternative text is intentional, no replacements there
    """

    skip_pages = ["Table of contents"]
    # article status templates, lowercase
    skip_templates = ["accuracy", "bad translation", "deletion", "expansion", "laptop style", "merge", "move", "out of date", "stub", "style", "translateme"]

    def __init__(self, api, cache_dir, interactive=False, first=None, title=None):
        self.api = api
        self.cache_dir = cache_dir
        self.interactive = interactive

        # parameters for self.run()
        self.first = first
        self.title = title

        # TODO: when there are many different changes, create a page on ArchWiki
        # describing the changes, link it with wikilink syntax using a generic
        # alternative text (e.g. "semi-automatic style fixes") (path should be
        # configurable, as well as the URL fallback)
        if interactive is True:
            self.edit_summary = "simplification and beautification of wikilinks, fixing whitespace, capitalization and section fragments (https://github.com/lahwaacz/wiki-scripts/blob/master/link-checker.py (interactive))"
        else:
            self.edit_summary = "simplification of wikilinks, fixing whitespace and section fragments (https://github.com/lahwaacz/wiki-scripts/blob/master/link-checker.py)"

        # ensure that we are authenticated
        require_login(self.api)

        # api.redirects_map() is not currently cached, save the result
        self.redirects = api.redirects_map()

        # mapping of canonical titles to displaytitles
        self.displaytitles = {}
        for ns in self.api.namespaces.keys():
            if ns < 0:
                continue
            for page in self.api.generator(generator="allpages", gaplimit="max", gapnamespace=ns, prop="info", inprop="displaytitle"):
                self.displaytitles[page["title"]] = page["displaytitle"]

        # cache of latest revisions' content
        self.db = ws.cache.LatestRevisionsText(api, self.cache_dir, autocommit=False)
        # create shallow copy of the db to trigger update only the first time
        # and not at every access
        self.db_copy = {}
        for ns in self.api.namespaces.keys():
            if ns >= 0:
                self.db_copy[str(ns)] = self.db[str(ns)]
        self.db.dump()


    @staticmethod
    def set_argparser(argparser):
        # first try to set options for objects we depend on
        present_groups = [group.title for group in argparser._action_groups]
        if "Connection parameters" not in present_groups:
            API.set_argparser(argparser)

        group = argparser.add_argument_group(title="script parameters")
        group.add_argument("-i", "--interactive", action="store_true",
                help="enables interactive mode")
        mode = group.add_mutually_exclusive_group()
        mode.add_argument("--first", default=None, metavar="TITLE",
                help="the title of the first page to be processed")
        mode.add_argument("--title",
                help="the title of the only page to be processed")

    @classmethod
    def from_argparser(klass, args, api=None):
        if api is None:
            api = API.from_argparser(args)
        return klass(api, args.cache_dir, interactive=args.interactive, first=args.first, title=args.title)


    def check_trivial(self, wikilink):
        """
        Perform trivial simplification, replace `[[Foo|foo]]` with `[[foo]]`.

        :param wikilink: instance of `mwparserfromhell.nodes.wikilink.Wikilink`
                         representing the link to be checked
        """
        # Wikicode.matches() ignores even the '#' character indicating relative links;
        # hence [[#foo|foo]] would be replaced with [[foo]]
        # Our canonicalize() function does exactly what we want and need.
        if wikilink.text is not None and canonicalize(wikilink.title) == canonicalize(wikilink.text):
            # title is mandatory, so the text becomes the title
            wikilink.title = wikilink.text
            wikilink.text = None

    def check_relative(self, wikilink, title, srcpage):
        """
        Use relative links whenever possible. For example, links to sections such as
        `[[Foo#Bar]]` on a page `title` are replaced with `[[#Bar]]` whenever `Foo`
        redirects to or is equivalent to `title`.

        :param wikilink: the link to be checked
        :type wikilink: :py:class:`mwparserfromhell.nodes.wikilink.Wikilink`
        :param title: the parsed :py:attr:`wikilink.title`
        :type title: :py:class:`mw.parser_helpers.title.Title`
        :param str srcpage: the title of the page being checked
        """
        if title.iwprefix or not title.sectionname:
            return
        # check if title is a redirect
        target = self.redirects.get(title.fullpagename)
        if target:
            _title = Title(self.api, target)
            _title.sectionname = title.sectionname
        else:
            _title = title

        if canonicalize(srcpage) == _title.fullpagename:
            wikilink.title = "#" + _title.sectionname
            title.parse(wikilink.title)

    def check_redirect_exact(self, wikilink, title):
        """
        Replace `[[foo|bar]]` with `[[bar]]` if `foo` and `bar` point to the
        same page after resolving redirects.

        :param wikilink: the link to be checked
        :type wikilink: :py:class:`mwparserfromhell.nodes.wikilink.Wikilink`
        :param title: the parsed :py:attr:`wikilink.title`
        :type title: :py:class:`mw.parser_helpers.title.Title`
        """
        if wikilink.text is None:
            return

        text = Title(self.api, wikilink.text)

        target1 = self.redirects.get(title.fullpagename)
        target2 = self.redirects.get(text.fullpagename)
        if target1 is not None:
            target1 = Title(self.api, target1)
            # bail out if we lost the fragment
            if target1.sectionname != title.sectionname:
                return
        if target2 is not None:
            target2 = Title(self.api, target2)

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
        if title.pagename == "Wpa supplicant":
            return

        # might be only a section, e.g. [[#foo]]
        if title.fullpagename:
            target = self.redirects.get(title.fullpagename)
            if target is not None and target.lower() == title.fullpagename.lower():
                wikilink.title = target
                if title.sectionname:
                    # TODO: check how canonicalization of section anchor works; previously we only replaced underscores
                    # (this is run only in interactive mode anyway)
                    wikilink.title = str(wikilink.title) + "#" + title.sectionname
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
        if not title.fullpagename:
            return
        # skip links to special namespaces
        if title.namespacenumber < 0:
            return
        # report pages without DISPLAYTITLE (red links)
        if title.fullpagename not in self.displaytitles:
            logger.warning("wikilink to non-existing page: {}".format(wikilink))
            return

        # FIXME: avoid stripping ":" in the [[:Category:...]] links
        if title.namespace == "Category":
            return

        # FIXME: very common false positive
        if title.pagename == "Wpa supplicant":
            return

        # assemble new title
        new = self.displaytitles[title.fullpagename]
        if title.sectionname:
            # NOTE: section anchor should be checked in self.check_anchor(), so
            #       canonicalization here does not matter
            new += "#" + title.sectionname

        # skip if only the case of the first letter is different
        if wikilink.title[1:] != new[1:]:
            wikilink.title = new
            title.parse(wikilink.title)

    def check_anchor(self, wikilink, title, srcpage):
        # TODO: beware of https://phabricator.wikimedia.org/T20431
        #   - mark with {{Broken fragment}} instead of reporting?
        #   - someday maybe: check N older revisions, section might have been renamed (must be interactive!) or moved to other page (just report)
        # FIXME:
        #   lookup for duplicated sections: e.g. [[Optical disc drive#DVD_2]]
        #   DISPLAYTITLE set in self.check_displaytitle() is dropped

        # we can't check interwiki links
        if title.iwprefix:
            return True

        # empty sectionname is always valid
        if title.sectionname == "":
            return True

        # lookup target page content
        # TODO: pulling revisions from cache does not expand templates
        #       (transclusions like on List of applications)
        if title.fullpagename:
            _target_ns = title.namespacenumber
            _target_title = title.fullpagename
        else:
            src_title = Title(self.api, srcpage)
            _target_ns = src_title.namespacenumber
            _target_title = src_title.fullpagename
        # skip links to special pages (e.g. [[Special:Preferences#mw-prefsection-rc]])
        if _target_ns < 0:
            return
        if _target_title in self.redirects:
            _new = self.redirects.get(_target_title)
            if "#" not in _new:
                _target_title = _new
            else:
                logger.warning("skipping {} (section fragment placed on a redirect to possibly different section)".format(wikilink))
                return
        pages = self.db_copy[str(_target_ns)]
        wrapped_titles = ws.utils.ListOfDictsAttrWrapper(pages, "title")
        try:
            page = ws.utils.bisect_find(pages, _target_title, index_list=wrapped_titles)
        except IndexError:
            logger.error("could not find content of page: '{}' (wikilink {})".format(_target_title, wikilink))
            return
        text = page["revisions"][0]["*"]

        # get lists of section headings and anchors
        headings = get_section_headings(text)
        if len(headings) == 0:
            logger.warning("link with broken section fragment: {}".format(wikilink))
            return
        anchors = get_anchors(headings)

        anchor = dotencode(title.sectionname)
        needs_fix = True

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
                return
            else:
                logger.warning("link with broken section fragment: {}".format(wikilink))
                return
        else:
            logger.warning("link with broken section fragment: {}".format(wikilink))
            return

        # assemble new section fragment
        new_fragment = strip_markup(headings[anchors.index(anchor)])
        # anchors can't contain '[' and ']', encode them manually
        new_fragment = new_fragment.replace("[", ".5B").replace("]", ".5D")

        # fix and/or beautify
        if wikilink.text is None:
            # TODO: simplify (see #25)
            t, _ = wikilink.title.split("#", maxsplit=1)
            wikilink.title = t + "#" + new_fragment
            title.parse(wikilink.title)
        # Avoid beautification if there is alternative text and the link
        # actually works. Otherwise use canonical form for the replacement.
        elif needs_fix is True:
            title.sectionname = new_fragment
            wikilink.title = str(title)

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

    def update_page(self, src_title, text):
        """
        Parse the content of the page and call various methods to update the links.

        :param str src_title: title of the page
        :param str text: content of the page
        :returns str: updated content
        """
        # FIXME: ideally "DeveloperWiki:" would be a proper namespace
        if src_title in self.skip_pages or src_title.startswith("DeveloperWiki:"):
            logger.info("Skipping blacklisted page [[{}]]".format(src_title))
            return text

        logger.info("Parsing page [[{}]] ...".format(src_title))
        wikicode = mwparserfromhell.parse(text)

        for wikilink in wikicode.ifilter_wikilinks(recursive=True):
            # skip links inside article status templates
            parent = wikicode.get(wikicode.index(wikilink, recursive=True))
            if isinstance(parent, mwparserfromhell.nodes.template.Template) and parent.name.lower() in self.skip_templates:
                continue

            title = Title(self.api, wikilink.title)
            # skip interlanguage links (handled by update-interlanguage-links.py)
            if title.iw in self.api.interlanguagemap.keys():
                continue

            self.collapse_whitespace_pipe(wikilink)
            self.check_trivial(wikilink)
            self.check_relative(wikilink, title, src_title)
            self.check_redirect_exact(wikilink, title)
            self.check_redirect_capitalization(wikilink, title)
            self.check_displaytitle(wikilink, title)
            self.check_anchor(wikilink, title, src_title)

            # partial second pass
            self.check_trivial(wikilink)
            self.check_redirect_exact(wikilink, title)

            # collapse whitespace around the link, e.g. 'foo [[ bar]]' -> 'foo [[bar]]'
            self.collapse_whitespace(wikicode, wikilink)

        return str(wikicode)

    def _edit(self, title, pageid, text_new, text_old, timestamp):
        if text_old != text_new:
            try:
                if self.interactive is False:
                    self.api.edit(title, pageid, text_new, timestamp, self.edit_summary, bot="")
                else:
                    edit_interactive(self.api, title, pageid, text_old, text_new, timestamp, self.edit_summary, bot="")
            except APIError as e:
                pass

    def process_page(self, title):
        result = self.api.call_api(action="query", prop="revisions", rvprop="content|timestamp", titles=title)
        page = list(result["pages"].values())[0]
        timestamp = page["revisions"][0]["timestamp"]
        text_old = page["revisions"][0]["*"]
        text_new = self.update_page(title, text_old)
        self._edit(title, page["pageid"], text_new, text_old, timestamp)

    def process_allpages(self, apfrom=None):
        for page in self.api.generator(generator="allpages", gaplimit="100", gapfilterredir="nonredirects", gapfrom=apfrom, prop="revisions", rvprop="content|timestamp"):
            title = page["title"]
            if lang.detect_language(title)[1] != "English":
                continue
            timestamp = page["revisions"][0]["timestamp"]
            text_old = page["revisions"][0]["*"]
            text_new = self.update_page(title, text_old)
            self._edit(title, page["pageid"], text_new, text_old, timestamp)

    def run(self):
        if self.title is not None:
            checker.process_page(self.title)
        else:
            checker.process_allpages(apfrom=self.first)


if __name__ == "__main__":
    import ws.config

    checker = ws.config.object_from_argparser(LinkChecker, description="Parse all pages on the wiki and try to fix/simplify/beautify links")

    try:
        checker.run()
    except InteractiveQuit:
        pass
