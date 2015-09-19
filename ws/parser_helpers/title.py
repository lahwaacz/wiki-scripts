#! /usr/bin/env python3

# TODO:
#   make interwiki prefixes more useful (local vs. external, interwiki vs. interlanguage)
#   ArchWiki-specific language detection
#   add examples to the module docstring

import re

from .encodings import _anchor_preprocess

__all__ = ["canonicalize", "Title"]

def canonicalize(title):
    """
    Return a canonical form of the title, that is:
    
    - underscores are replaced with spaces,
    - leading and trailing whitespace is stripped,
    - consecutive spaces are squashed,
    - first letter is capitalized.

    .. note::
        The interwiki and namespace prefixes are not split, canonicalization
        is applied to the passed title as a whole.

    :param title: a :py:obj:`str` or :py:class:`mwparserfromhell.wikicode.Wikicode` object
    :returns: a :py:obj:`str` object
    """
    title = str(title).replace("_", " ").strip()
    title = re.sub("( )+", "\g<1>", title)
    if title == "":
        return ""
    title = title[0].upper() + title[1:]
    return title

class Title:
    """
    A helper class intended for easy manipulation with wiki titles. Title
    parsing complies to the rules used in `MediaWiki code`_ and the interface is
    inspired by the `magic words`_. Besides namespace detection, we also parse
    interwiki prefixes, which is useful for parsing the wiki links on lower
    level than what :py:mod:`mwparserfromhell` provides (it does not take the
    wiki configuration into account). The functionality depends on the
    :py:class:`API <ws.core.api.API>` class for the validation of interwiki and
    namespace prefixes.

    .. _`MediaWiki code`: https://www.mediawiki.org/wiki/Manual:Title.php#Title_structure
    .. _`magic words`: https://www.mediawiki.org/wiki/Help:Magic_words#Page_names
    """

    def __init__(self, api, title):
        """
        :param api: an :py:class:`API <ws.core.api.API>` instance
        :param title: a :py:obj:`str` or :py:class:`mwparserfromhell.wikicode.Wikicode` object
        """
        self.api = api

        # Interwiki prefix (e.g. ``wikipedia``), lowercase
        self.iw = None
        # Namespace, in the canonical form (e.g. ``ArchWiki talk``)
        self.ns = None
        # Pure title (i.e. without interwiki and namespace prefixes), in the
        # canonical form (see :py:func:`canonicalize`)
        self.pure = None
        # Section anchor
        self.anchor = None

        self.parse(title)

    @staticmethod
    def _find_caseless(what, where, from_target=False):
        """
        Do a case-insensitive search in a list/iterable.

        :param what: element to be found
        :param where: a list/iterable for searching
        :param from_target: if True, return the element from the list/iterable instead of ``what``
        :raises ValueError: when not found
        """
        _what = what.lower()
        for item in where:
            if item.lower() == _what:
                if from_target is True:
                    return item
                return what
        raise ValueError

    def parse(self, full_title):
        """
        Splits the title into ``(iwprefix, namespace, pagename, sectionname)``
        parts and canonicalizes them. Can be used to set these attributes from
        a string of full title instead of creating new instance.

        :param str full_title: The full title to be parsed.
        """
        full_title = str(full_title)

        # parse interwiki prefix
        try:
            iw, _rest = full_title.lstrip(":").split(":", maxsplit=1)
            iw = iw.lower().replace("_", "").strip()
            # check if it is valid interwiki prefix
            self.iw = self._find_caseless(iw, self.api.interwikimap.keys())
        except ValueError:
            self.iw = ""
            _rest = full_title

        # parse namespace
        try:
            ns, _pure = _rest.lstrip(":").split(":", maxsplit=1)
            ns = ns.replace("_", " ").strip()
            if self.iw == "" or "local" in self.api.interwikimap[self.iw]:
                # check if it is valid namespace
                # TODO: API.namespaces does not consider namespace aliases
                self.ns = self._find_caseless(ns, self.api.namespaces.values(), from_target=True)
            else:
                self.ns = ns
        except ValueError:
            self.ns = ""
            _pure = _rest

        # TODO: This is not entirely MediaWiki-like, perhaps we should just
        # throw BadTitle exception. In that case other bad titles should be
        # reported as well.
        _pure = _pure.lstrip(":")

        # split section anchor
        try:
            _pure, anchor = _pure.split("#", maxsplit=1)
        except ValueError:
            anchor = ""

        # canonicalize title
        self.pure = canonicalize(_pure)
        # canonicalize anchor
        self.anchor = _anchor_preprocess(anchor)

    def _format(self, pre, mid, title):
        if pre and mid:
            return "{}:{}:{}".format(pre, mid, title)
        elif pre:
            return "{}:{}".format(pre, title)
        elif mid:
            return "{}:{}".format(mid, title)
        else:
            return title

    @property
    def iwprefix(self):
        """
        The interwiki prefix of the title.
        """
        return self.iw


    @property
    def namespace(self):
        """
        Same as ``{{NAMESPACE}}``.
        """
        return self.ns

    @property
    def namespacenumber(self):
        """
        Same as ``{{NAMESPACENUMBER}}``.
        """
        ns_inv = dict( (v,k) for k,v in self.api.namespaces.items() )
        return ns_inv[self.ns]

    @property
    def articlespace(self):
        """
        Same as ``{{ARTICLESPACE}}``.
        """
        ns_id = self.namespacenumber
        if ns_id % 2 == 0:
            return self.ns
        return self.api.namespaces[ns_id - 1]

    @property
    def talkspace(self):
        """
        Same as ``{{TALKSPACE}}``.
        """
        ns_id = self.namespacenumber
        if ns_id % 2 == 1:
            return self.ns
        return self.api.namespaces[ns_id + 1]


    @property
    def pagename(self):
        """
        Same as ``{{PAGENAME}}``, drops the interwiki and namespace prefixes.
        The section anchor is not included. Other ``*pagename`` attributes are
        based on this attribute.
        """
        return self.pure

    @property
    def fullpagename(self):
        """
        Same as ``{{FULLPAGENAME}}``, but also includes interwiki prefix (if any).
        """
        return self._format(self.iwprefix, self.namespace, self.pagename)

    @property
    def basepagename(self):
        """
        Same as ``{{BASEPAGENAME}}``, drops the interwiki and namespace prefixes
        and the rightmost subpage level.
        """
        base = self.pagename.rsplit("/", maxsplit=1)[0]
        return base

    @property
    def subpagename(self):
        """
        Same as ``{{SUBPAGENAME}}``, returns the rightmost subpage level.
        """
        subpage = self.pagename.rsplit("/", maxsplit=1)[-1]
        return subpage

    @property
    def rootpagename(self):
        """
        Same as ``{{ROOTPAGENAME}}``, drops the interwiki and namespace prefixes
        and all subpages.
        """
        base = self.pagename.split("/", maxsplit=1)[0]
        return base

    @property
    def articlepagename(self):
        """
        Same as ``{{ARTICLEPAGENAME}}``.
        """
        return self._format(self.iwprefix, self.articlespace, self.pagename)

    @property
    def talkpagename(self):
        """
        Same as ``{{TALKPAGENAME}}``.
        """
        return self._format(self.iwprefix, self.talkspace, self.pagename)


    @property
    def sectionname(self):
        """
        The section anchor, usable in wiki links. It is passed through the
        :py:func:`ws.parser_helpers.encodings._anchor_preprocess` function,
        but it is not anchor-encoded nor decoded.

        .. note::
            Section anchors on MediaWiki are usually encoded (see
            :py:func:`ws.parser_helpers.encodings.dotencode`), but decoding is
            ambiguous due to whitespace squashing and the fact that the escape
            character itself (i.e. the dot) is not encoded even when followed by
            two hex characters. As a result, the canonical form of the anchor
            cannot be determined without comparing to the existing sections of
            the target page.
        """
        return self.anchor


    @iwprefix.setter
    def iwprefix(self, value):
        if isinstance(value, str):
            try:
                self.iw = self._find_caseless(value, self.api.interwikimap.keys())
            except ValueError:
                if value == "":
                    self.iw = value
                else:
                    raise ValueError("tried to assign invalid interwiki prefix: {}".format(value))
        else:
            raise TypeError("iwprefix must be of type 'str'")

    @namespace.setter
    def namespace(self, value):
        if isinstance(value, str):
            try:
                self.ns = self._find_caseless(canonicalize(value), self.api.namespaces.values(), from_target=True)
            except ValueError:
                raise ValueError("tried to assign invalid namespace: {}".format(value))
        else:
            raise TypeError("namespace must be of type 'str'")

# TODO: disallow interwiki and namespace prefixes and section anchor
    @pagename.setter
    def pagename(self, value):
        if isinstance(value, str):
            self.pure = canonicalize(value)
        else:
            raise TypeError("pagename must be of type 'str'")

    @sectionname.setter
    def sectionname(self, value):
        if isinstance(value, str):
            self.anchor = _anchor_preprocess(value)
        else:
            raise TypeError("sectionname must be of type 'str'")


    def __repr__(self):
        return "{}('{}')".format(self.__class__, self)

    def __str__(self):
        """
        Returns the full representation of the title in the canonical form.
        """
        if self.sectionname:
            return "{}#{}".format(self._format(self.iwprefix, self.namespace, self.pagename), self.sectionname)
        return self._format(self.iwprefix, self.namespace, self.pagename)
