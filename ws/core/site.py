#! /usr/bin/env python3

from .meta import Meta
from ..utils import LazyProperty

class Site(Meta):
    """
    The :py:class:`Site` class holds information about the wiki site.

    Valid properties are listed in the :py:attr:`properties` attribute, which is
    accessed by the :py:meth:`__getattr__ <ws.core.meta.Meta>` method. The
    representation these `automatic` properties is the same as returned by the
    `MediaWiki API`_, unless it is overridden by an explicit method of the same
    name in this class.

    All :py:attr:`properties` are evaluated lazily and cached. The cache is
    never automatically invalidated, you should create a new instance for this.

    .. _`MediaWiki API`: https://www.mediawiki.org/wiki/API:Siteinfo
    """

    module = "siteinfo"
    properties = {"general", "namespaces", "namespacealiases", "specialpagealiases",
            "magicwords", "interwikimap", "dbrepllag", "statistics", "usergroups",
            "libraries", "extensions", "fileextensions", "rightsinfo", "restrictions",
            "languages", "skins", "extensiontags", "functionhooks", "showhooks",
            "variables", "protocols", "defaultoptions"}

    def __init__(self, api):
        super().__init__(api)

    @property
    def interwikimap(self):
        """
        Interwiki prefixes on the wiki, represented as a dictionary where
        keys are the available prefixes and additional information (as returned
        by the `siteinfo/interwikimap` API query).
        """
        interwikis = self.__getattr__("interwikimap")
        return dict( (d["prefix"], d) for d in interwikis )

    @property
    def interlanguagemap(self):
        """
        Interlanguage prefixes on the wiki, filtered from the general
        :py:attr:`interwikimap <ws.core.API.interwikimap>` property.
        """
        return dict( (prefix, info) for prefix, info in self.interwikimap.items() if "local" in info )

    @property
    def namespaces(self):
        """
        Namespaces represented as a mapping (dictionary) of namespace IDs to
        dictionaries with information returned by the API.
        """
        namespaces = self.__getattr__("namespaces")
        return dict( (ns["id"], ns) for ns in namespaces.values() )

    @property
    def namespacealiases(self):
        """
        Namespace aliases represented as a mapping (dictionary) of namespace
        names to dictionaries with information returned by the API.
        """
        namespacealiases = self.__getattr__("namespacealiases")
        return dict( (d["*"], d) for d in namespacealiases )

    @property
    def namespacenames(self):
        """
        Mapping of all valid namespace names, including canonical names and
        aliases, to the corresponding namespace ID.
        """
        names = dict( (ns["*"], ns["id"]) for ns in self.namespaces.values() )
        names.update(dict( (ns["canonical"], ns["id"]) for ns in self.namespaces.values() if "canonical" in ns ))
        names.update(dict( (ns["*"], ns["id"]) for ns in self.namespacealiases.values() ))
        return names

    # TODO: solve caching of methods with unhashable parameters somehow
#    @lru_cache(maxsize=8)
    def redirects_map(self, source_namespaces=None, target_namespaces="all"):
        """
        Build a mapping of redirects in given namespaces. Interwiki redirects are
        not included in the mapping.

        Note that the mapping can contain double redirects, which could cause
        some algorithms to break.

        :param source_namespaces:
            the namespace ID of the source title must be in this list in order
            to be included in the mapping (default is ``[0]``, the magic word
            ``"all"`` will select all available namespaces)
        :param target_namespaces:
            the namespace ID of the target title must be in this list in order
            to be included in the mapping (default is ``"all"``, which will
            select all available namespaces)
        :returns:
            a dictionary where the keys are source titles and values are the
            redirect targets, including the link fragments (e.g.
            ``"Page title#Section title"``).
        """
        source_namespaces = source_namespaces if source_namespaces is not None else [0]
        if source_namespaces == "all":
            source_namespaces = [ns for ns in self.namespaces if int(ns) >= 0]
        if target_namespaces == "all":
            target_namespaces = [ns for ns in self.namespaces if int(ns) >= 0]

        redirects = {}
        for ns in target_namespaces:
            # FIXME: adding the rdnamespace parameter causes an internal API error,
            # see https://wiki.archlinux.org/index.php/User:Lahwaacz/Notes#API:_resolving_redirects
            # removing it for now, all namespaces are included by default anyway...
#            allpages = self._api.generator(generator="allpages", gapnamespace=ns, gaplimit="max", prop="redirects", rdprop="title|fragment", rdnamespace="|".join(source_namespaces), rdlimit="max")
            allpages = self._api.generator(generator="allpages", gapnamespace=ns, gaplimit="max", prop="redirects", rdprop="title|fragment", rdlimit="max")
            for page in allpages:
                # construct the mapping, the query result is somewhat reversed...
                target_title = page["title"]
                for redirect in page.get("redirects", []):
                    source_title = redirect["title"]
                    target_fragment = redirect.get("fragment")
                    if target_fragment:
                        redirects[source_title] = "{}#{}".format(target_title, target_fragment)
                    else:
                        redirects[source_title] = target_title
        return redirects
