#! /usr/bin/env python3

import re

# only for explicit type check in Title.parse
import mwparserfromhell

from .encodings import _anchor_preprocess, urldecode
from ..utils import find_caseless

__all__ = ["canonicalize", "Title", "InvalidTitleCharError"]

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

    # explicit setters are necessary, because methods decorated with
    # @foo.setter are not callable from self.__init__
    def set_iwprefix(self, iw):
        if not isinstance(iw, str):
            raise TypeError("iwprefix must be of type 'str'")

        try:
            # strip spaces
            iw = iw.replace("_", " ").strip()
            # convert spaces to underscores to make find_caseless work
            # TODO: this is not tested, just a wild guess
            iw = iw.replace(" ", "_")
            # check if it is valid interwiki prefix
            self.iw = find_caseless(iw, self.api.site.interwikimap.keys(), from_target=True)
        except ValueError:
            if iw == "":
                self.iw = iw
            else:
                raise ValueError("tried to assign invalid interwiki prefix: {}".format(iw))

    def set_namespace(self, ns):
        if not isinstance(ns, str):
            raise TypeError("namespace must be of type 'str'")

        try:
            ns = canonicalize(ns)
            if self.iw == "" or "local" in self.api.site.interwikimap[self.iw]:
                # check if it is valid namespace
                self.ns = find_caseless(ns, self.api.site.namespacenames, from_target=True)
            else:
                self.ns = ns
        except ValueError:
            raise ValueError("tried to assign invalid namespace: {}".format(ns))

    def set_pagename(self, pagename):
        if not isinstance(pagename, str):
            raise TypeError("pagename must be of type 'str'")

        # TODO: This is not entirely MediaWiki-like, perhaps we should just
        # throw BadTitle exception.
        pagename = pagename.lstrip(":")

        # MediaWiki does not treat encoded underscores as spaces (e.g.
        # [[Main%5Fpage]] is rendered as <a href="...">Main_page</a>),
        # but we focus on meaning, not rendering.
        pagename = urldecode(pagename)
        # FIXME: how does MediaWiki handle unicode titles?  https://phabricator.wikimedia.org/T139881
        # as a workaround, any UTF-8 character, which is not an ASCII character, is allowed
        if re.search("[^{}\\u0100-\\uFFFF]".format(self.api.site.general["legaltitlechars"]), pagename):
            raise InvalidTitleCharError("Given title contains illegal character(s): '{}'".format(pagename))
        # canonicalize title
        self.pure = canonicalize(pagename)

    def set_sectionname(self, sectionname):
        if not isinstance(sectionname, str):
            raise TypeError("sectionname must be of type 'str'")

        # canonicalize anchor
        self.anchor = _anchor_preprocess(sectionname)

    def parse(self, full_title):
        """
        Splits the title into ``(iwprefix, namespace, pagename, sectionname)``
        parts and canonicalizes them. Can be used to set these attributes from
        a string of full title instead of creating new instance.

        :param full_title:
            The full title to be parsed, either a :py:obj:`str` or
            :py:class:`mwparserfromhell.wikicode.Wikicode` object.
        """
        # Wikicode has to be converted to str, but we don't want to convert
        # numbers or any arbitrary objects.
        if not isinstance(full_title, str) and not isinstance(full_title, mwparserfromhell.wikicode.Wikicode):
            raise TypeError("full_title must be either 'str' or 'Wikicode'")
        full_title = str(full_title)

        # parse interwiki prefix
        try:
            iw, _rest = full_title.lstrip(":").split(":", maxsplit=1)
            self.set_iwprefix(iw)
        except ValueError:
            self.iw = ""
            _rest = full_title

        # parse namespace
        try:
            ns, _pure = _rest.lstrip(":").split(":", maxsplit=1)
            self.set_namespace(ns)
        except ValueError:
            self.ns = ""
            _pure = _rest

        # split section anchor
        try:
            _pure, anchor = _pure.split("#", maxsplit=1)
        except ValueError:
            anchor = ""

        self.set_pagename(_pure)
        self.set_sectionname(anchor)

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
        return self.api.site.namespacenames[self.ns]

    @property
    def articlespace(self):
        """
        Same as ``{{ARTICLESPACE}}``.
        """
        ns_id = self.namespacenumber
        if ns_id % 2 == 0:
            return self.ns
        return self.api.site.namespaces[ns_id - 1]["*"]

    @property
    def talkspace(self):
        """
        Same as ``{{TALKSPACE}}``.
        """
        ns_id = self.namespacenumber
        if ns_id % 2 == 1:
            return self.ns
        return self.api.site.namespaces[ns_id + 1]["*"]


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

        .. note::
            The ``$wgNamespacesWithSubpages`` option is ignored (not available
            via API anyway), the property behaves as if subpages were enabled
            for all namespaces.
        """
        base = self.pagename.rsplit("/", maxsplit=1)[0]
        return base

    @property
    def subpagename(self):
        """
        Same as ``{{SUBPAGENAME}}``, returns the rightmost subpage level.

        .. note::
            The ``$wgNamespacesWithSubpages`` option is ignored (not available
            via API anyway), the property behaves as if subpages were enabled
            for all namespaces.
        """
        subpage = self.pagename.rsplit("/", maxsplit=1)[-1]
        return subpage

    @property
    def rootpagename(self):
        """
        Same as ``{{ROOTPAGENAME}}``, drops the interwiki and namespace prefixes
        and all subpages.

        .. note::
            The ``$wgNamespacesWithSubpages`` option is ignored (not available
            via API anyway), the property behaves as if subpages were enabled
            for all namespaces.
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
        return self.set_iwprefix(value)

    @namespace.setter
    def namespace(self, value):
        return self.set_namespace(value)

    @pagename.setter
    def pagename(self, value):
        if not isinstance(value, str):
            raise TypeError("pagename must be of type 'str'")

        iw, ns, pure, anchor = self.iw, self.ns, self.pure, self.anchor
        self.iw, self.ns, self.pure, self.anchor = None, None, None, None
        try:
            self.parse(value)
        except InvalidTitleCharError:
            self.iw, self.ns, self.pure, self.anchor = iw, ns, pure, anchor
            raise
        if (self.iw and not iw) or (self.ns and not ns) or self.anchor:
            self.iw, self.ns, self.pure, self.anchor = iw, ns, pure, anchor
            raise ValueError("tried to assign invalid pagename: {}".format(value))
        self.iw, self.ns, self.anchor = iw, ns, anchor

        # Set again with set_pagename, because e.g. if self.ns was initially
        # "Help" and the user sets pagename to "Help:Foo", the result should be
        # "Help:Help:Foo". This is not possible with plain self.parse above,
        # because that way the second "Help:" would be stripped.
        self.set_pagename(value)

    @sectionname.setter
    def sectionname(self, value):
        return self.set_sectionname(value)


    def __eq__(self, other):
        return self.api.api_url == other.api.api_url and \
               self.iw == other.iw and \
               self.ns == other.ns and \
               self.pure == other.pure and \
               self.anchor == other.anchor

    def __repr__(self):
        return "{}('{}')".format(self.__class__, self)

    def __str__(self):
        """
        Returns the full representation of the title in the canonical form.
        """
        if self.sectionname:
            return "{}#{}".format(self._format(self.iwprefix, self.namespace, self.pagename), self.sectionname)
        return self._format(self.iwprefix, self.namespace, self.pagename)


class InvalidTitleCharError(Exception):
    """
    Raised when an invalid title is passed to :py:class:`Title`.
    """
    pass
