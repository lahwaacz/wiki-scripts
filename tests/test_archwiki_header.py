#! /usr/bin/env python3

from nose.tools import assert_equals, raises
from nose.plugins.skip import SkipTest

import mwparserfromhell

from ws.ArchWiki.header import *

class test_fix_header():
    @staticmethod
    def _do_test(snippet, expected):
        wikicode = mwparserfromhell.parse(snippet)
        fix_header(wikicode)
        assert_equals(str(wikicode), expected)

    def test_fixed_point(self):
        snippet = """\
{{DISPLAYTITLE:foo}}
{{Lowercase title}}
[[Category:foo]]
[[category:bar]]
[[cs:foo]]
[[en:foo]]
Some text

== Section ==

Text...
"""
        self._do_test(snippet, snippet)

    def test_no_text(self):
        snippet = """\
{{out of date}}
[[Category:ASUS]]
==Hardware==
"""
        expected = """\
[[Category:ASUS]]
{{out of date}}
==Hardware==
"""
        self._do_test(snippet, expected)

    def test_lowercase_title(self):
        snippet = """\
{{Lowercase_title}}
"""
        expected = """\
{{Lowercase_title}}
"""
        self._do_test(snippet, expected)

    def test_lowercase_title_2(self):
        snippet = """\
{{Lowercase title}}
[[en:Main page]]
text
"""
        expected = """\
{{Lowercase title}}
[[en:Main page]]
text
"""
        self._do_test(snippet, expected)

    def test_whitespace_stripping(self):
        snippet = """\
{{Lowercase title}}

[[Category:foo]]  

[[en:foo]]

[[Category:bar]]
  
Some text...
"""
        expected = """\
{{Lowercase title}}
[[Category:foo]]
[[Category:bar]]
[[en:foo]]
Some text...
"""
        self._do_test(snippet, expected)

    def test_vi(self):
        snippet = """\
The [[vi]] editor.
"""
        self._do_test(snippet, snippet)

    def test_notoc(self):
        # TODO: failing because mwparserfromhell can't parse behavior switches
        raise SkipTest
        snippet = """\
__NOTOC__
[[es:Main page]]
Text of the first paragraph...
"""
        self._do_test(snippet, snippet)

    def test_toc(self):
        snippet = """\
__TOC__
[[es:Main page]]
Text of the first paragraph...
"""
        expected = """\
[[es:Main page]]
__TOC__
Text of the first paragraph...
"""
        self._do_test(snippet, expected)

    # FIXME: remove_and_squash is broken
    def test_full(self):
        snippet = """\
Some text with [[it:langlinks]] inside.

[[Category:foo]]
This [[category:foo|catlink]] is a typo.
[[en:bar]]

Some other text [[link]]
[[category:bar]]
[[cs:some page]]

{{DISPLAYTITLE:lowercase title}}
{{Lowercase title}}
"""
        expected = """\
{{DISPLAYTITLE:lowercase title}}
{{Lowercase title}}
[[Category:foo]]
[[category:bar]]
[[cs:some page]]
[[en:bar]]
[[it:langlinks]]
Some text with inside.

This [[category:foo|catlink]] is a typo.

Some other text [[link]]

"""
        self._do_test(snippet, expected)

    def test_noinclude(self):
        snippet = """\
<noinclude>{{Template}}
[[en:Template:Foo]]
</noinclude>
<includeonly>Template content...</includeonly>
"""
        expected = """\
<noinclude>
{{Template}}
[[en:Template:Foo]]
</noinclude>
<includeonly>Template content...</includeonly>
"""
        self._do_test(snippet, expected)

    @raises(HeaderError)
    def test_noinclude_error(self):
        snippet = """\
[[cs:Template:Foo]]
<noinclude>{{Template}}
[[en:Template:Foo]]
</noinclude>
<includeonly>Template content...</includeonly>
"""
        wikicode = mwparserfromhell.parse(snippet)
        fix_header(wikicode)
