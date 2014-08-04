#! /usr/bin/env python3

import difflib
from pygments import highlight
from pygments.lexers.text import DiffLexer
from pygments.formatters import Terminal256Formatter

def diff_highlighted(old, new, fromfile="", tofile="", fromfiledate="", tofiledate=""):
    """
    Generic wrapper around :py:func:`difflib.unified_diff` with highlighter based
    on :py:mod:`pygments`.

    See `difflib.unified_diff` for description of optional parameters.

    :param old: text to compare (old revision)
    :param new: text to compare (new revision)
    :param fromfile: original file name (used as meta data to format diff header)
    :param tofile: new file name (used as meta data to format diff header)
    :param fromfiledate: original file timestamp (used as meta data to format diff header)
    :param tofiledate: new file timestamp (used as meta data to format diff header)
    
    .. _`difflib.unified_diff`: https://docs.python.org/3/library/difflib.html#difflib.unified_diff
    """
    # splitlines() omits the '\n' char from each line, so we need to
    # explicitly set lineterm="", otherwise spacing would be inconsistent
    diff = difflib.unified_diff(old.splitlines(), new.splitlines(), fromfile, tofile, fromfiledate, tofiledate, lineterm="")

    text = "\n".join(diff)
    lexer = DiffLexer()
    formatter = Terminal256Formatter()
    return highlight(text, lexer, formatter)

class RevisionDiffer:
    """
    Object for comparing revisions.

    :param api: a :py:class:`MediaWiki.API` instance to operate on
    """
    def __init__(self, api):
        self.api = api

    def diff(self, oldrevid, newrevid):
        """
        Method to get highlighted diff of two revisions. Uses ANSI color sequences
        for output in a 256-color terminal.

        Basic meta data (title, username, timestamp and comment) is included in the
        diff header. Original *unified diff* format supports only file name and
        timestamp fields, we show more.

        :param oldrevid: revision ID for old revision
        :param newrevid: revision ID for new revision
        """
        # query content + meta data for each revision
        result = self.api.call(action="query", prop="revisions", rvprop="content|timestamp|user|comment", revids="%s|%s" % (oldrevid, newrevid))
        page = list(result["pages"].values())[0]    # returned structure is the same as for generators

        title = page["title"]
        if len(page["revisions"]) != 2:
            raise Exception("API returned wrong number of revisions, are the revision IDs valid?")
        rev_old = page["revisions"][0]
        rev_new = page["revisions"][1]
        # fields to show in header (extended, abusing original field titles)
        fn_old = "%s\t(%s)" % (title, rev_old["user"])
        fn_new = "%s\t(%s)" % (title, rev_new["user"])
        ts_old = "%s\t%s" % (rev_old["timestamp"], rev_old["comment"])
        ts_new = "%s\t%s" % (rev_new["timestamp"], rev_new["comment"])

        return diff_highlighted(rev_old["*"], rev_new["*"], fn_old, fn_new, ts_old, ts_new)
