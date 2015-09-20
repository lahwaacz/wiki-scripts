#! /usr/bin/env python3

try:
    import WikEdDiff
    _has_wikeddiff = True
except ImportError:
    _has_wikeddiff = False
    import difflib
    try:
        import pygments
        import pygments.lexers.text
        import pygments.formatters
        _has_pygments = True
    except ImportError:
        _has_pygments = False

def diff_highlighted(old, new, fromfile="", tofile="", fromfiledate="", tofiledate=""):
    """
    Returns a diff between two texts formatted with ANSI color sequences
    suitable for output in 256-color terminal.

    When available, the :py:mod:`WikEdDiff` library and its
    :py:class:`AnsiFormatter` is used. Otherwise the :py:mod:`difflib`
    module from the standard library is used to generate the diff in unified
    format and :py:mod:`pygments` is used (when available) as the highlighter.

    :param old: text to compare (old revision)
    :param new: text to compare (new revision)
    :param fromfile: original file name (used as meta data to format diff header)
    :param tofile: new file name (used as meta data to format diff header)
    :param fromfiledate: original file timestamp (used as meta data to format diff header)
    :param tofiledate: new file timestamp (used as meta data to format diff header)
    :returns: diff formatted with ANSI color sequences
    """
    if _has_wikeddiff is True:
        # get diff fragments
        config = WikEdDiff.WikEdDiffConfig()
        wd = WikEdDiff.WikEdDiff(config)
        fragments = wd.diff(old, new)

        # format with ANSI colors
        formatter = WikEdDiff.AnsiFormatter()
        diff_ansi = formatter.format( fragments, coloredBlocks=True )

        # prepend metadata
        header = formatter.pushColor(formatter.color_delete) + \
                 "--- {}\t{}".format(fromfile, fromfiledate) + \
                 formatter.popColor() + "\n" + \
                 formatter.pushColor(formatter.color_insert) + \
                 "+++ {}\t{}".format(tofile, tofiledate) + \
                 formatter.popColor() + "\n"
        sep = formatter.pushColor(formatter.color_separator) + \
              formatter.separator_symbol + \
              formatter.popColor()
        return header + sep + "\n" + diff_ansi + "\n" + sep

    else:
        # splitlines() omits the '\n' char from each line, so we need to
        # explicitly set lineterm="", otherwise spacing would be inconsistent
        diff = difflib.unified_diff(old.splitlines(), new.splitlines(), fromfile, tofile, fromfiledate, tofiledate, lineterm="")

        text = "\n".join(diff)
        if _has_pygments is True:
            lexer = pygments.lexers.text.DiffLexer()
            formatter = pygments.formatters.Terminal256Formatter()
            text = pygments.highlight(text, lexer, formatter)
        return text

class RevisionDiffer:
    """
    Object for comparing revisions.

    :param api: a :py:class:`MediaWiki.api.API` instance to operate on
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
        result = self.api.call_api(action="query", prop="revisions", rvprop="content|timestamp|user|comment", revids="%s|%s" % (oldrevid, newrevid))
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
