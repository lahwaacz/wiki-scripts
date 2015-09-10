#! /usr/bin/env python3

# TODO:
#   make interwiki prefixes more useful (accessing, changing, local vs. external, interwiki vs. interlanguage)
#   ArchWiki-specific language detection

import re

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

        # The full title as passed to the constructor
        self.full_title = str(title)
        # Interwiki prefix (e.g. ``wikipedia``), lowercase
        self.iw = None
        # Namespace, in the canonical form (e.g. ``ArchWiki talk``)
        self.ns = None
        # Pure title (i.e. without interwiki and namespace prefixes), in the
        # canonical form (see :py:func:`canonicalize`)
        self.pure = None

        self._parse()

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

    def _parse(self):
        """
        Splits the title into ``(iw, ns, pure)`` parts and canonicalizes them.
        """
        # parse interwiki prefix (defaults to "" in __init__)
        try:
            iw, _rest = self.full_title.split(":", maxsplit=1)
            iw = iw.lower().replace("_", "").strip()
            # check if it is valid interwiki prefix
            self.iw = self._find_caseless(iw, self.api.interwikimap.keys())
        except ValueError:
            self.iw = ""
            _rest = self.full_title

        # parse namespace
        # TODO: API.namespaces does not consider namespace aliases
        try:
            ns, _pure = _rest.split(":", maxsplit=1)
            ns = ns.replace("_", " ").strip()
            # check if it is valid namespace
            self.ns = self._find_caseless(ns, self.api.namespaces.values(), from_target=True)
        except ValueError:
            self.ns = ""
            _pure = _rest

        # canonicalize title
        self.pure = canonicalize(_pure)

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
    def fullpagename(self):
        """
        Same as ``{{FULLPAGENAME}}``, but also includes interwiki prefix (if any).
        """
        return self._format(self.iw, self.ns, self.pure)

    @property
    def pagename(self):
        """
        Same as ``{{PAGENAME}}``, drops the interwiki and namespace prefixes.
        """
        return self.pure

    @property
    def basepagename(self):
        """
        Same as ``{{BASEPAGENAME}}``, drops the interwiki and namespace prefixes
        and the rightmost subpage level.
        """
        base = self.pure.rsplit("/", maxsplit=1)[0]
        return base

    @property
    def subpagename(self):
        """
        Same as ``{{SUBPAGENAME}}``, returns the rightmost subpage level.
        """
        subpage = self.pure.rsplit("/", maxsplit=1)[-1]
        return subpage

    @property
    def rootpagename(self):
        """
        Same as ``{{ROOTPAGENAME}}``, drops the interwiki and namespace prefixes
        and all subpages.
        """
        base = self.pure.split("/", maxsplit=1)[0]
        return base

    @property
    def articlepagename(self):
        """
        Same as ``{{ARTICLEPAGENAME}}``.
        """
        return self._format(self.iw, self.articlespace, self.pure)

    @property
    def talkpagename(self):
        """
        Same as ``{{TALKPAGENAME}}``.
        """
        return self._format(self.iw, self.talkspace, self.pure)


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
