import pytest

from ws.parser_helpers.title import (
    Context,
    DatabaseTitleError,
    InvalidColonError,
    InvalidTitleCharError,
    Title,
    canonicalize,
)


class test_canonicalize:
    # keys: input, values: expected result
    titles = {
        "": "",
        " _  ": "",
        "Foo_bar": "Foo bar",
        " Foo_bar__": "Foo bar",
        " foo   _ bar__": "Foo bar",
        "foo": "Foo",
        "foo:bar": "Foo:bar",
        "fOOo BaAar": "FOOo BaAar",
    }

    @pytest.mark.parametrize("src, expected", titles.items())
    def test(self, src: str, expected: tuple[str, str]) -> None:
        result = canonicalize(src)
        assert result == expected


class test_title:
    # keys: input, values: dictionary of expected attributes of the Title object
    titles = {
        # test splitting and fullpagename formatting
        "Foo:Bar:Baz#section": {
            "iwprefix": "",
            "namespace": "",
            "pagename": "Foo:Bar:Baz",
            "sectionname": "section",
            "fullpagename": "Foo:Bar:Baz",
            "leading_colon": "",
        },
        "Talk:Foo": {
            "iwprefix": "",
            "namespace": "Talk",
            "pagename": "Foo",
            "sectionname": "",
            "fullpagename": "Talk:Foo",
            "leading_colon": "",
        },
        "en:Main page": {
            "iwprefix": "en",
            "namespace": "",
            "pagename": "Main page",
            "sectionname": "",
            "fullpagename": "en:Main page",
            "leading_colon": "",
        },
        "en:help:style#section": {
            "iwprefix": "en",
            "namespace": "Help",
            "pagename": "Style",
            "sectionname": "section",
            "fullpagename": "en:Help:Style",
            "leading_colon": "",
        },
        # test stripping whitespace around colons
        "en : help : style # section": {
            "iwprefix": "en",
            "namespace": "Help",
            "pagename": "Style",
            "sectionname": "section",
            "fullpagename": "en:Help:Style",
            "leading_colon": "",
        },
        # test canonicalization
        "helP_ Talk : foo  _Bar_": {
            "iwprefix": "",
            "namespace": "Help talk",
            "pagename": "Foo Bar",
            "sectionname": "",
            "fullpagename": "Help talk:Foo Bar",
            "leading_colon": "",
        },
        # test anchor canonicalization
        "Main page #  _foo_  ": {
            "pagename": "Main page",
            "sectionname": "foo",
        },
        "#  _foo_  ": {
            "pagename": "",
            "sectionname": "foo",
        },
        # test MediaWiki-like properties
        "foo": {
            "fullpagename": "Foo",
            "pagename": "Foo",
            "basepagename": "Foo",
            "subpagename": "Foo",
            "rootpagename": "Foo",
            "articlepagename": "Foo",
            "talkpagename": "Talk:Foo",
            "namespace": "",
            "namespacenumber": 0,
            "articlespace": "",
            "talkspace": "Talk",
        },
        "talk:foo": {
            "fullpagename": "Talk:Foo",
            "pagename": "Foo",
            "basepagename": "Foo",
            "subpagename": "Foo",
            "rootpagename": "Foo",
            "articlepagename": "Foo",
            "talkpagename": "Talk:Foo",
            "namespace": "Talk",
            "namespacenumber": 1,
            "articlespace": "",
            "talkspace": "Talk",
        },
        "help talk:foo/Bar/baz": {
            "fullpagename": "Help talk:Foo/Bar/baz",
            "namespace": "Help talk",
            "pagename": "Foo/Bar/baz",
            "basepagename": "Foo/Bar",
            "subpagename": "baz",
            "rootpagename": "Foo",
        },
        "Help talk:Style": {
            "articlepagename": "Help:Style",
            "talkpagename": "Help talk:Style",
            "namespace": "Help talk",
            "namespacenumber": 13,
            "articlespace": "Help",
            "talkspace": "Help talk",
            "pagename": "Style",
        },
        "Help:Style": {
            "articlepagename": "Help:Style",
            "talkpagename": "Help talk:Style",
            "namespace": "Help",
            "namespacenumber": 12,
            "articlespace": "Help",
            "talkspace": "Help talk",
            "pagename": "Style",
        },
        # test local/external namespaces
        "en:Foo:Bar": {
            "iwprefix": "en",
            "namespace": "",
            "pagename": "Foo:Bar",
            "fullpagename": "en:Foo:Bar",
            "leading_colon": "",
        },
        "en:Talk:Bar": {
            "iwprefix": "en",
            "namespace": "Talk",
            "pagename": "Bar",
            "fullpagename": "en:Talk:Bar",
            "leading_colon": "",
        },
        "wikipedia:Foo:Bar": {
            "iwprefix": "wikipedia",
            "namespace": "",
            "pagename": "Foo:Bar",
            "fullpagename": "wikipedia:Foo:Bar",
            "leading_colon": "",
        },
        # test alternative namespace names
        "Project:Foo": {
            "iwprefix": "",
            "namespace": "Project",
            "pagename": "Foo",
            "fullpagename": "Project:Foo",
            "leading_colon": "",
        },
        "Image:Foo": {
            "iwprefix": "",
            "namespace": "Image",
            "pagename": "Foo",
            "fullpagename": "Image:Foo",
            "leading_colon": "",
        },
        # test colons
        ":Category:Foo": {
            "iwprefix": "",
            "namespace": "Category",
            "pagename": "Foo",
            "fullpagename": "Category:Foo",
            "leading_colon": ":",
        },
        "Foo::Bar": {
            "iwprefix": "",
            "namespace": "",
            "pagename": "Foo::Bar",
            "fullpagename": "Foo::Bar",
            "leading_colon": "",
        },
        "::Help:Style": InvalidColonError,
        "::wikipedia:Wikipedia:Manual of Style": InvalidColonError,
        "wikipedia::Wikipedia:Manual of Style": {
            "iwprefix": "wikipedia",
            "namespace": "",
            "pagename": "Wikipedia:Manual of Style",
            "fullpagename": "wikipedia:Wikipedia:Manual of Style",
            "leading_colon": "",
        },
        "wikipedia::Foo": {
            "iwprefix": "wikipedia",
            "namespace": "",
            "pagename": "Foo",
            "fullpagename": "wikipedia:Foo",
            "leading_colon": "",
        },
        "Help::Style": InvalidColonError,
        "Wikipedia:Code::Blocks": {
            "iwprefix": "wikipedia",
            "namespace": "",
            "pagename": "Code::Blocks",
            "fullpagename": "wikipedia:Code::Blocks",
        },
        # "double" namespace (important mainly for setters)
        "Help:Help:Style": {
            "iwprefix": "",
            "namespace": "Help",
            "pagename": "Help:Style",
            "fullpagename": "Help:Help:Style",
            "leading_colon": "",
        },
        "en:en:Style": {
            "iwprefix": "en",
            "namespace": "",
            "pagename": "En:Style",
            "fullpagename": "en:En:Style",
            "leading_colon": "",
        },
    }

    @pytest.mark.parametrize("src, expected", titles.items())
    def test_constructor(
        self,
        title_context: Context,
        src: str,
        expected: dict[str, str] | type[Exception],
    ) -> None:
        if isinstance(expected, type):
            with pytest.raises(expected):
                title = Title(title_context, src)
        else:
            title = Title(title_context, src)
            for attr, value in expected.items():
                assert getattr(title, attr) == value

    @pytest.mark.parametrize("src, expected", titles.items())
    def test_parse(
        self,
        title_context: Context,
        src: str,
        expected: dict[str, str] | type[Exception],
    ) -> None:
        if isinstance(expected, type):
            title = Title(title_context, "")
            with pytest.raises(expected):
                title.parse(src)
        else:
            title = Title(title_context, "")
            title.parse(src)
            for attr, value in expected.items():
                assert getattr(title, attr) == value

    @pytest.mark.parametrize("full, attrs", titles.items())
    def test_setters(
        self,
        title_context: Context,
        full: str,
        attrs: dict[str, str] | type[Exception],
    ) -> None:
        if not isinstance(attrs, type):
            expected = Title(title_context, full)
            title = Title(title_context, "")
            title.iwprefix = attrs.get("iwprefix", "")
            title.namespace = attrs.get("namespace", "")
            title.pagename = attrs.get("pagename", "")
            title.sectionname = attrs.get("sectionname", "")
            assert title == expected


class test_title_setters:
    attributes = ["iwprefix", "namespace", "pagename", "sectionname"]

    @staticmethod
    @pytest.fixture(scope="function")
    def title(title_context: Context) -> Title:
        return Title(title_context, "en:Help:Style#section")

    @pytest.mark.parametrize("attr", attributes)
    def test_invalid_type(self, title: Title, attr: str) -> None:
        with pytest.raises(TypeError):
            setattr(title, attr, 42)

    def test_invalid_type_constructor(self, title_context: Context) -> None:
        with pytest.raises(TypeError):
            Title(title_context, 42)  # type: ignore[arg-type]

    def test_invalid_type_parse(self, title: Title) -> None:
        with pytest.raises(TypeError):
            title.parse(42)  # type: ignore[arg-type]

    # this one has to be explicit for completeness, because
    # `title.pagename = foo` checks it too
    def test_invalid_type_set_pagename(self, title: Title) -> None:
        with pytest.raises(TypeError):
            title._set_pagename(42)  # type: ignore[arg-type]

    def test_iwprefix(self, title: Title) -> None:
        assert title.iwprefix == "en"
        assert str(title) == "en:Help:Style#section"
        # test internal tag
        title.iwprefix = "cs"
        assert title.iwprefix == "cs"
        assert str(title) == "cs:Help:Style#section"
        # test external tag
        title.iwprefix = "de"
        assert title.iwprefix == "de"
        assert str(title) == "de:Help:Style#section"
        # test empty
        title.iwprefix = ""
        assert title.iwprefix == ""
        assert str(title) == "Help:Style#section"

    def test_namespace(self, title: Title) -> None:
        assert title.namespace == "Help"
        assert str(title) == "en:Help:Style#section"
        # test talkspace
        title.namespace = title.talkspace
        assert title.namespace == "Help talk"
        assert str(title) == "en:Help talk:Style#section"
        # test empty
        title.namespace = ""
        assert title.namespace == ""
        assert str(title) == "en:Style#section"

    def test_pagename(self, title: Title) -> None:
        assert title.pagename == "Style"
        assert str(title) == "en:Help:Style#section"
        # test simple
        title.pagename = "Main page"
        assert title.pagename == "Main page"
        assert str(title) == "en:Help:Main page#section"

    @pytest.mark.parametrize(
        "pagename", ["en:Main page", "Help:Foo", "Main page#Section"]
    )
    def test_invalid_pagename(self, title_context: Context, pagename: str) -> None:
        title = Title(title_context, "")
        with pytest.raises(ValueError):
            title.pagename = pagename

    def test_sectionname(self, title: Title) -> None:
        assert title.sectionname == "section"
        assert str(title) == "en:Help:Style#section"
        # test simple
        title.sectionname = "another section"
        assert title.sectionname == "another section"
        assert str(title) == "en:Help:Style#another section"

    def test_eq(self, title_context: Context, title: Title) -> None:
        other_title = Title(title_context, "")
        other_title.iwprefix = "en"
        other_title.namespace = "Help"
        other_title.pagename = "Style"
        other_title.sectionname = "section"
        assert other_title == title

    def test_str_repr(self, title: Title) -> None:
        title.iwprefix = ""
        title.namespace = ""
        title.pagename = "Main page"
        title.sectionname = ""
        assert str(title) == "Main page"
        assert repr(title) == "<class 'ws.parser_helpers.title.Title'>('Main page')"

    def test_invalid_iwprefix(self, title: Title) -> None:
        with pytest.raises(ValueError):
            title.iwprefix = "invalid prefix"

    def test_invalid_namespace(self, title: Title) -> None:
        with pytest.raises(ValueError):
            title.namespace = "invalid namespace"


class test_title_valid_chars:
    invalid_titles = [
        "Foo [bar]",
        "Foo | bar",
        "<foo>",
        "foo %23 bar",  # encoded '#'
        "{foo}",
        # whitespace
        "Foo\0bar",  # null
        "Foo\bbar",  # backspace
        "Foo\tbar",  # horizontal tab
        "Foo\nbar",  # line feed
        "Foo\vbar",  # vertical tab
        "Foo\fbar",  # form feed
        "Foo\rbar",  # carriage return
    ]

    valid_titles = [
        "Foo\u0085bar",  # next line
        "Foo\u00A0bar",  # no-break space
        "Foo\u1680bar",  # Ogham space mark
        "Foo\u2000bar",  # en quad
        "Foo\u2001bar",  # em quad
        "Foo\u2002bar",  # en space
        "Foo\u2003bar",  # em space
        "Foo\u2004bar",  # three-per-em space
        "Foo\u2005bar",  # four-per-em space
        "Foo\u2006bar",  # six-per-em space
        "Foo\u2007bar",  # figure space
        "Foo\u2008bar",  # punctuation space
        "Foo\u2009bar",  # thin space
        "Foo\u200Abar",  # hair space
        "Foo\u2028bar",  # line separator
        "Foo\u2029bar",  # paragraph separator
        "Foo\u202Fbar",  # narrow no-break space
        "Foo\u205Fbar",  # medium mathematical space
        "Foo\u3000bar",  # ideographic space
        # detected as problematic
        "Table of contents (العربية)",
        "Let’s Encrypt",  # note that it's not an apostrophe!
    ]

    @pytest.mark.parametrize("pagename", invalid_titles)
    def test_invalid_chars(self, title_context: Context, pagename: str) -> None:
        with pytest.raises(InvalidTitleCharError):
            Title(title_context, pagename)

    @pytest.mark.parametrize("pagename", invalid_titles)
    def test_invalid_chars_setter(self, title_context: Context, pagename: str) -> None:
        title = Title(title_context, "")
        with pytest.raises(InvalidTitleCharError):
            title.pagename = pagename

    @pytest.mark.parametrize("pagename", valid_titles)
    def test_valid_chars(self, title_context: Context, pagename: str) -> None:
        title = Title(title_context, pagename)
        assert title.pagename == pagename

    @pytest.mark.parametrize("pagename", valid_titles)
    def test_valid_chars_setter(self, title_context: Context, pagename: str) -> None:
        title = Title(title_context, "")
        title.pagename = pagename
        assert title.pagename == pagename


class test_dbtitle:
    titles = [
        ("main page", 0, "Main page"),
        ("talk:main page", 1, "Main page"),
        ("talk:main page", 0, "Talk:Main page"),
    ]
    titles_error = [
        "Wikipedia:Main page",
        "Wikipedia:Talk:Main page",
        "Foo#Bar",
    ]

    @pytest.mark.parametrize("src", titles)
    def test_dbtitle(self, title_context: Context, src: tuple[str, int, str]) -> None:
        src_title, ns, expected = src
        title = Title(title_context, src_title)
        assert title.dbtitle(ns) == expected

    @pytest.mark.parametrize("src", titles_error)
    def test_dbtitle_error(self, title_context: Context, src: str) -> None:
        title = Title(title_context, src)
        with pytest.raises(DatabaseTitleError):
            title.dbtitle()


class test_make_absolute:
    titles = [
        ("Talk:Foo", "Bar", "Talk:Foo"),
        ("Wikipedia:Foo", "Bar", "wikipedia:Foo"),
        ("#Bar", "Foo", "Foo#Bar"),
        ("Foo#Bar", "Baz", "Foo#Bar"),
        ("/Bar", "Foo", "Foo/Bar"),
        ("Foo/Bar", "Baz", "Foo/Bar"),
        (":/Foo", "Bar", "/Foo"),
        # MW incompatibility: MediaWiki does not allow "../" links from top-level pages
        ("../Foo", "Bar", "Foo"),
        ("../Foo", "Bar/Baz", "Bar/Foo"),
        ("../../Foo", "A/B/C", "A/Foo"),
        # MW incompatibility: MediaWiki does not allow "/./" in the middle of a link
        ("/Foo/./Bar", "Baz", "Baz/Foo/Bar"),
    ]

    @pytest.mark.parametrize("src", titles)
    def test_make_absolute(self, title_context: Context, src: tuple[str, str, str]) -> None:
        src_title, base_title, expected = src
        title = Title(title_context, src_title)
        result = title.make_absolute(base_title)
        assert str(result) == expected
        assert result is not title

    def test_valueerror(self, title_context: Context) -> None:
        title = Title(title_context, "en:Foo")
        with pytest.raises(ValueError):
            title.make_absolute(title)


def test_format(title_context: Context) -> None:
    title = Title(title_context, ":En:talk:main page#section")
    assert title.format() == "Main page"
    assert title.format(colon=True) == ":Main page"
    assert title.format(iwprefix=True) == "en:Talk:Main page"
    assert title.format(iwprefix=True, namespace=False) == "en:Talk:Main page"
    assert title.format(namespace=True) == "Talk:Main page"
    assert title.format(sectionname=True) == "Main page#section"
    assert title.format(colon=True, iwprefix=True) == ":en:Talk:Main page"
    assert (
        title.format(colon=True, iwprefix=True, sectionname=True)
        == ":en:Talk:Main page#section"
    )
