#! /usr/bin/env python3

import re
from copy import deepcopy

# only for explicit type check in Title.parse
import mwparserfromhell

from .encodings import _anchor_preprocess, urldecode
from ..utils import find_caseless

__all__ = ["canonicalize", "Context", "Title", "InvalidTitleCharError"]

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

class Context:
    """
    A context class for the :py:class:`Title` parser.

    The parameters can be fetched either from the
    :py:class:`API <ws.client.api.API>` or
    :py:class:`Database <ws.db.database.Database>` class:

    :param dict interwikimap:
        a mapping representing the data from MediaWiki's ``interwiki`` table
    :param dict namespacenames:
        a dictionary mapping namespace names to numbers
    :param dict namespaces:
        a dictionary mapping namespace numbers to dictionaries providing details
        about the namespace, such as names or case-sensitiveness
    :param str legaltitlechars:
        string of characters which are allowed to occur in page titles

    Normally, the user does not interact with the :py:class:`Context` class.
    Both the API and Database classes provide shortcut functions
    (:py:func:`API.Title <ws.client.api.API.Title>` and
    :py:func:`Database.Title <ws.db.database.Database.Title>`, respectively)
    which construct the necessary context and pass it to the
    :py:class:`Title` class.
    """
    def __init__(self, interwikimap, namespacenames, namespaces, legaltitlechars):
        self.interwikimap = interwikimap
        self.namespacenames = namespacenames
        self.namespaces = namespaces
        self.legaltitlechars = legaltitlechars

    @classmethod
    def from_api(klass, api):  # pragma: no cover
        """
        Creates a :py:class:`Context` instance using the
        :py:class:`API <ws.client.api.API>` object.

        Used by :py:func:`API.Title <ws.client.api.API.Title>`.
        """
        # drop unnecessary information which is not stored in the database
        # (this allows comparison with database-context titles)
        iwmap = deepcopy(api.site.interwikimap)
        for key, data in iwmap.items():
            if "language" in data:
                del data["language"]

        return klass(
            iwmap,
            api.site.namespacenames,
            api.site.namespaces,
            api.site.general["legaltitlechars"],
        )

    def __eq__(self, other):  # pragma: no cover
        """
        Standard equality comparison operator. Comparing API-based and
        Database-based contexts is possible.
        """
        return self.interwikimap == other.interwikimap and \
               self.namespacenames == other.namespacenames and \
               self.namespaces == other.namespaces and \
               self.legaltitlechars == other.legaltitlechars

class Title:
    """
    A helper class intended for easy manipulation with wiki titles. Title
    parsing complies to the rules used in `MediaWiki code`_ and the interface is
    inspired by the `magic words`_. Besides namespace detection, we also parse
    interwiki prefixes, which is useful for parsing the wiki links on lower
    level than what :py:mod:`mwparserfromhell` provides (it does not take the
    wiki configuration into account). The functionality depends on the
    :py:class:`Context` class for the validation of interwiki and namespace
    prefixes.

    .. _`MediaWiki code`: https://www.mediawiki.org/wiki/Manual:Title.php#Title_structure
    .. _`magic words`: https://www.mediawiki.org/wiki/Help:Magic_words#Page_names
    """

    def __init__(self, context, title):
        """
        :param Context context:
            a context object for the parser
        :param title:
            a :py:obj:`str` or :py:class:`mwparserfromhell.wikicode.Wikicode` object

        The ``title`` is parsed by the :py:meth:`parse` method.
        """
        self.context = context

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
    def _set_iwprefix(self, iw):
        """
        Auxiliary setter for ``iwprefix``.
        """
        if not isinstance(iw, str):
            raise TypeError("iwprefix must be of type 'str'")

        try:
            # strip spaces
            iw = iw.replace("_", " ").strip()
            # convert spaces to underscores to make find_caseless work
            # TODO: this is not tested, just a wild guess
            iw = iw.replace(" ", "_")
            # check if it is valid interwiki prefix
            self.iw = find_caseless(iw, self.context.interwikimap.keys(), from_target=True)
        except ValueError:
            if iw == "":
                self.iw = iw
            else:
                raise ValueError("tried to assign invalid interwiki prefix: {}".format(iw))

    def _set_namespace(self, ns):
        """
        Auxiliary setter for ``namespace``.
        """
        if not isinstance(ns, str):
            raise TypeError("namespace must be of type 'str'")

        try:
            ns = canonicalize(ns)
            if self.iw == "" or "local" in self.context.interwikimap[self.iw]:
                # check if it is valid namespace
                self.ns = find_caseless(ns, self.context.namespacenames, from_target=True)
            else:
                self.ns = ns
        except ValueError:
            raise ValueError("tried to assign invalid namespace: {}".format(ns))

    def _set_pagename(self, pagename):
        """
        Auxiliary setter for ``pagename``.
        """
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
        if re.search("[^{}\\u0100-\\uFFFF]".format(self.context.legaltitlechars), pagename):
            raise InvalidTitleCharError("Given title contains illegal character(s): '{}'".format(pagename))
        # canonicalize title
        self.pure = canonicalize(pagename)

    def _set_sectionname(self, sectionname):
        """
        Auxiliary setter for ``sectionname``.
        """
        if not isinstance(sectionname, str):
            raise TypeError("sectionname must be of type 'str'")

        # canonicalize anchor
        self.anchor = _anchor_preprocess(sectionname)

    def _format(self, pre, mid, title):
        """
        Auxiliary method for full title formatting.
        """
        if pre and mid:
            return "{}:{}:{}".format(pre, mid, title)
        elif pre:
            return "{}:{}".format(pre, title)
        elif mid:
            return "{}:{}".format(mid, title)
        else:
            return title

    def parse(self, full_title):
        """
        Splits the title into ``(iwprefix, namespace, pagename, sectionname)``
        parts and canonicalizes them. Can be used to set these attributes from
        a string of full title instead of creating new instance.

        :param full_title:
            The full title to be parsed, either a :py:obj:`str` or
            :py:class:`mwparserfromhell.wikicode.Wikicode` object.
        :raises:
            :py:exc:`InvalidTitleCharError` when the page title is not valid
        """
        # Wikicode has to be converted to str, but we don't want to convert
        # numbers or any arbitrary objects.
        if not isinstance(full_title, str) and not isinstance(full_title, mwparserfromhell.wikicode.Wikicode):
            raise TypeError("full_title must be either 'str' or 'Wikicode'")
        full_title = str(full_title)

        # parse interwiki prefix
        try:
            iw, _rest = full_title.lstrip(":").split(":", maxsplit=1)
            self._set_iwprefix(iw)
        except ValueError:
            self.iw = ""
            _rest = full_title

        # parse namespace
        try:
            ns, _pure = _rest.lstrip(":").split(":", maxsplit=1)
            self._set_namespace(ns)
        except ValueError:
            self.ns = ""
            _pure = _rest

        # split section anchor
        try:
            _pure, anchor = _pure.split("#", maxsplit=1)
        except ValueError:
            anchor = ""

        self._set_pagename(_pure)
        self._set_sectionname(anchor)

    @property
    def iwprefix(self):
        """
        The interwiki prefix of the title.

        This attribute has a setter which raises :py:exc:`ValueError` when the
        supplied interwiki prefix is not valid.
        """
        return self.iw

    @iwprefix.setter
    def iwprefix(self, value):
        return self._set_iwprefix(value)


    @property
    def namespace(self):
        """
        Same as ``{{NAMESPACE}}`` in MediaWiki.

        This attribute has a setter which raises :py:exc:`ValueError` when the
        supplied namespace is not valid.
        """
        return self.ns

    @namespace.setter
    def namespace(self, value):
        return self._set_namespace(value)

    @property
    def namespacenumber(self):
        """
        Same as ``{{NAMESPACENUMBER}}`` in MediaWiki.
        """
        return self.context.namespacenames[self.ns]

    @property
    def articlespace(self):
        """
        Same as ``{{ARTICLESPACE}}`` in MediaWiki.
        """
        ns_id = self.namespacenumber
        if ns_id % 2 == 0:
            return self.ns
        return self.context.namespaces[ns_id - 1]["*"]

    @property
    def talkspace(self):
        """
        Same as ``{{TALKSPACE}}`` in MediaWiki.
        """
        ns_id = self.namespacenumber
        if ns_id % 2 == 1:
            return self.ns
        return self.context.namespaces[ns_id + 1]["*"]


    @property
    def pagename(self):
        """
        Same as ``{{PAGENAME}}`` in MediaWiki, drops the interwiki and namespace
        prefixes. The section anchor is not included. Other ``*pagename``
        attributes are based on this attribute.

        This attribute has a setter which calls :py:meth:`parse` to split the
        supplied page name.
        """
        return self.pure

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

        # Set again with _set_pagename, because e.g. if self.ns was initially
        # "Help" and the user sets pagename to "Help:Foo", the result should be
        # "Help:Help:Foo". This is not possible with plain self.parse above,
        # because that way the second "Help:" would be stripped.
        self._set_pagename(value)

    @property
    def fullpagename(self):
        """
        Same as ``{{FULLPAGENAME}}`` in MediaWiki, but also includes interwiki
        prefix (if any).
        """
        return self._format(self.iwprefix, self.namespace, self.pagename)

    @property
    def basepagename(self):
        """
        Same as ``{{BASEPAGENAME}}`` in MediaWiki, drops the interwiki and
        namespace prefixes and the rightmost subpage level.

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
        Same as ``{{SUBPAGENAME}}`` in MediaWiki, returns the rightmost subpage
        level.

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
        Same as ``{{ROOTPAGENAME}}`` in MediaWiki, drops the interwiki and
        namespace prefixes and all subpages.

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
        Same as ``{{ARTICLEPAGENAME}}`` in MediaWiki.
        """
        return self._format(self.iwprefix, self.articlespace, self.pagename)

    @property
    def talkpagename(self):
        """
        Same as ``{{TALKPAGENAME}}`` in MediaWiki.
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

        This attribute has a setter.
        """
        return self.anchor

    @sectionname.setter
    def sectionname(self, value):
        return self._set_sectionname(value)


    def dbtitle(self, expected_ns=None):
        """
        Returns the title formatted for use in the database.

        In practice it is something between :py:attr:`pagename` and
        :py:attr:`fullpagename` to cover all the corner cases:

        - If there is an interwiki prefix, it is included. Necessary for old
          log entries from times when the current interwiki prefixes were not
          in place.
        - Namespace prefix is stripped if there is no interwiki prefix *and*
          the parsed namespace number agrees with ``expected_ns``. This is to
          cover the creation of new namespaces, e.g. pages ``Foo:Bar`` existing
          first in the main namespace and then moved into a separate namespace,
          ``Foo:``.
        - Section anchor is included. Again necessary for old log entries,
          apparently MediaWiki allowed ``#`` in user names at some point.

        :param int expected_ns: expected namespace number
        """
        if not self.iw and (expected_ns is None or self.namespacenumber == expected_ns):
            title = self._format("", "", self.pagename)
        else:
            title = self.fullpagename
            # it's not an interwiki prefix -> capitalize first letter
            title = title[0].upper() + title[1:]
        if self.sectionname:
            title += "#" + self.sectionname
        return title


    def make_absolute(self, basetitle):
        """
        Changes a relative link to an absolute link. Has no effect if called on
        an absolute link.

        Types of a relative link:

        - same-page section links (e.g. ``[[#Section name]]`` on page ``Base``
          is changed to ``[[Foo#Section name]]``)
        - subpages (e.g. ``[[/Subpage]]`` on page ``Base`` is changed to
          ``[[Base/Subpage]]``)

        :param basetitle:
            the base title, either :py:class:`str` or :py:class:`Title`
        :returns: ``None``, the ``self`` object is updated in place
        """
        if not isinstance(basetitle, Title):
            basetitle = Title(self.context, basetitle)
        if basetitle.iwprefix:
            raise ValueError("basetitle must not be interwiki link")

        # interwiki and namespace prefixes must be empty, otherwise it is not a relative link
        if self.iwprefix or self.namespace:
            return

        # handle same-page section links
        if not self.pagename:
            self.namespace = basetitle.namespace
            self.pagename = basetitle.pagename

        # handle subpages
        if self.pagename.startswith("/"):
            self.namespace = basetitle.namespace
            self.pagename = basetitle.pagename + self.pagename


    def __eq__(self, other):
        return self.context == other.context and \
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
