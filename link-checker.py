#! /usr/bin/env python3

# FIXME:
#   how hard is skipping code blocks? https://wiki.archlinux.org/index.php?title=Silent_boot&diff=376237&oldid=372833
#   wikilink nodes (title + text) should always be wikicode, we are assigning str, which might cause trouble

# TODO:
#   extlink -> wikilink conversion should be done first
#   URL-decoding (for page titles), dot-decoding (for sections)?
#   skip interwiki links, categories, interlanguage links
#   look at DISPLAYTITLE of the target page when replacing underscores (needs caching of latest revisions for performance)
#   capitalization of fragments (needs caching of latest revisions for performance)

import argparse
import os.path
import re

import mwparserfromhell

from MediaWiki import API, diff_highlighted
from MediaWiki.exceptions import *
from MediaWiki.interactive import *
import ArchWiki.lang as lang

def canonicalize(title):
    title = title.strip()
    title = title[0].upper() + title[1:]
    title = title.replace("_", " ")
    return title

class LinkChecker:
    def __init__(self, api, interactive=False):
        self.api = api
        self.interactive = interactive
        if interactive is True:
            self.edit_summary = "simplification of wikilinks, fixing whitespace and capitalization, removing underscores (https://github.com/lahwaacz/wiki-scripts/blob/master/link-checker.py (interactive))"
        else:
            self.edit_summary = "simplification of wikilinks, fixing whitespace (https://github.com/lahwaacz/wiki-scripts/blob/master/link-checker.py)"
        # namespaces of the links to be checked
        self.backlink_namespaces = ["0", "4", "12"]

        # get list of pageids of redirect pages
        print("Fetching redirects...")
        pageids = []
        for ns in self.backlink_namespaces:
            pages = api.generator(generator="allpages", gaplimit="max", gapfilterredir="redirects", gapnamespace=ns)
            _pageids = [str(page["pageid"]) for page in pages]
            pageids.extend(_pageids)

        # resolve redirects
        redirects = api.resolve_redirects(*pageids)

        # build dictionary
        self.redirects = {}
        for r in redirects:
            origin = r["from"]
            target = "{}#{}".format(r["to"], r["tofragment"]) if "tofragment" in r else r["to"]
            self.redirects[origin] = target

    def check_trivial(self, wikilink):
        """
        Perform trivial simplification, replace `[[Foo|foo]]` with `[[foo]]`.
        In interactive mode, underscores in the wikilink title are replaced with
        spaces if there is no alternative text.

        :param wikilink: instance of `mwparserfromhell.nodes.wikilink.Wikilink`
                         representing the link to be checked
        """
        # Replacing underscores is not safe, do it only in interactive mode.
        # Also not replacing if there is an alternative text to avoid largescale edits;
        # underscores in alternative text are likely intentional so replace only the title.
        if self.interactive is True and wikilink.text is None:
            try:
                wikilink.title = str(wikilink.title).replace("_", " ")
            except ValueError:
                pass

        # Wikicode.matches() ignores even the '#' character indicating relative links;
        # hence [[#foo|foo]] would be replaced with [[foo]]
        # Our canonicalize() function does exactly what we want and need.
        if wikilink.text is not None and canonicalize(wikilink.title) == canonicalize(wikilink.text):
            # title is mandatory, so the text becomes the title
            wikilink.title = wikilink.text
            wikilink.text = None

    def check_relative(self, wikilink, title):
        """
        Use relative links whenever possible. For example, links to sections such as
        `[[Foo#Bar]]` on a page `Foo` are replaced with `[[#Bar]]`.

        :param wikilink: instance of `mwparserfromhell.nodes.wikilink.Wikilink`
                         representing the link to be checked
        :param title: instance of `str` representing the title of the page being
                      checked
        """
        try:
            _title, _section = wikilink.title.split("#", maxsplit=1)
            if _title and _section and canonicalize(title) == canonicalize(_title):
                wikilink.title = "#" + _section
        except ValueError:
            # raised when unpacking failed
            pass

    def check_redirect_exact(self, wikilink):
        """
        Replace `[[foo|bar]]` with `[[bar]]` if `foo` and `bar` point to the same page
        after resolving redirects.

        :param wikilink: instance of `mwparserfromhell.nodes.wikilink.Wikilink`
                         representing the link to be checked
        """
        if wikilink.text is None:
            return

        # canonicalize link parts
        _title = canonicalize(wikilink.title)
        _text = canonicalize(wikilink.text)

        target1 = self.redirects.get(_title)
        target2 = self.redirects.get(_text)
        if target1 is not None and target2 is not None:
            if target1 == target2:
                wikilink.title = wikilink.text
                wikilink.text = None
        elif target1 is not None:
            if target1 == _text:
                wikilink.title = wikilink.text
                wikilink.text = None
        elif target2 is not None:
            if target2 == _title:
                wikilink.title = wikilink.text
                wikilink.text = None

    def check_redirect_capitalization(self, wikilink):
        """
        Avoid redirect iff the difference is only in capitalization.

        :param wikilink: instance of `mwparserfromhell.nodes.wikilink.Wikilink`
                         representing the link to be checked
        """
        try:
            _title, _section = wikilink.title.split("#", maxsplit=1)
        except:
            _title = wikilink.title
            _section = None
        # might be only a section, e.g. [[#foo]]
        if _title:
            _title = canonicalize(_title)
            target = self.redirects.get(_title)
            if target is not None and target.lower() == _title.lower():
                wikilink.title = target
                if _section:
                    wikilink.title = str(wikilink.title) + "#" + _section

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

    def update_page(self, title, text):
        """
        Parse the content of the page and call various methods to update the links.

        :param title: title of the page (as `str`)
        :param text: content of the page (as `str`)
        :returns: updated content (as `str`)
        """
        print("Parsing '%s'..." % title)
        wikicode = mwparserfromhell.parse(text)

        for wikilink in wikicode.ifilter_wikilinks(recursive=True):
            self.collapse_whitespace_pipe(wikilink)
            self.check_trivial(wikilink)
            self.check_relative(wikilink, title)
            self.check_redirect_exact(wikilink)
            if self.interactive is True:
                self.check_redirect_capitalization(wikilink)
            # collapse whitespace around the link, e.g. 'foo [[ bar]]' -> 'foo [[bar]]'
            self.collapse_whitespace(wikicode, wikilink)

        return str(wikicode)

    def process_page(self, title):
        result = self.api.call(action="query", prop="revisions", rvprop="content|timestamp", titles=title)
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

    def _edit(self, title, pageid, text_new, text_old, timestamp):
        if text_old != text_new:
            print("Editing '%s'" % title)
            try:
                if self.interactive is False:
                    self.api.edit(pageid, text_new, timestamp, self.edit_summary, bot="")
                else:
                    edit_interactive(self.api, pageid, text_old, text_new, timestamp, self.edit_summary, bot="")
            except (APIError, APIWarnings):
                print("error: failed to edit page '%s'" % title)


# any path, the dirname part must exist (e.g. path to a file that will be created in the future)
def arg_dirname_must_exist(string):
    dirname = os.path.split(string)[0]
    if not os.path.isdir(dirname):
        raise argparse.ArgumentTypeError("directory '%s' does not exist" % dirname)
    return string

# path to existing directory
def arg_existing_dir(string):
    if not os.path.isdir(string):
        raise argparse.ArgumentTypeError("directory '%s' does not exist" % string)
    return string


if __name__ == "__main__":
    argparser = argparse.ArgumentParser(description="Parse all pages on the wiki and try to fix/simplify/beautify links")

    _api = argparser.add_argument_group(title="API parameters")
    _api.add_argument("--api-url", default="https://wiki.archlinux.org/api.php", metavar="URL",
            help="the URL to the wiki's api.php (default: %(default)s)")
    _api.add_argument("--cookie-path", type=arg_dirname_must_exist, default=os.path.expanduser("~/.cache/ArchWiki.bot.cookie"), metavar="PATH",
            help="path to cookie file (default: %(default)s)")
    _api.add_argument("--ssl-verify", default=1, choices=(0, 1),
            help="whether to verify SSL certificates (default: %(default)s)")

    _script = argparser.add_argument_group(title="script parameters")
    _script.add_argument("-i", "--interactive", action="store_true",
            help="enables interactive mode")
    _mode = _script.add_mutually_exclusive_group()
    _mode.add_argument("--first", default=None, metavar="TITLE",
            help="the title of the first page to be processed")
    _mode.add_argument("--title",
            help="the title of the only page to be processed")

    args = argparser.parse_args()

    # retype from int to bool
    args.ssl_verify = True if args.ssl_verify == 1 else False

    api = API(args.api_url, cookie_file=args.cookie_path, ssl_verify=args.ssl_verify)
    # ensure that we are authenticated
    require_login(api)

    checker = LinkChecker(api, args.interactive)
    if args.title:
        checker.process_page(args.title)
    else:
        checker.process_allpages(apfrom=args.first)
