from typing import TYPE_CHECKING, Any, Generator, cast

from .meta import Meta

if TYPE_CHECKING:  # pragma: no cover
    from .api import API


class Site(Meta):
    """
    The :py:class:`Site` class holds information about the wiki site.

    Valid properties are listed in the :py:attr:`properties` attribute, which is
    accessed by the :py:meth:`__getattr__ <ws.client.meta.Meta>` method. The
    representation these `automatic` properties is the same as returned by the
    `MediaWiki API`_, unless it is overridden by an explicit method of the same
    name in this class.

    All :py:attr:`properties` are evaluated lazily and cached. The cache is
    never automatically invalidated, you should create a new instance for this.

    .. _`MediaWiki API`: https://www.mediawiki.org/wiki/API:Siteinfo
    """

    module = "siteinfo"
    properties = {
        "general",
        "namespaces",
        "namespacealiases",
        "specialpagealiases",
        "magicwords",
        "interwikimap",
        "dbrepllag",
        "statistics",
        "usergroups",
        "libraries",
        "extensions",
        "fileextensions",
        "rightsinfo",
        "restrictions",
        "languages",
        "languagevariants",
        "skins",
        "extensiontags",
        "functionhooks",
        "showhooks",
        "variables",
        "protocols",
        "defaultoptions",
        "uploaddialog",
    }

    def __init__(self, api: "API"):
        super().__init__(api)

    @property
    def interwikimap(self) -> dict[str, dict[str, str]]:
        """
        Interwiki prefixes on the wiki, represented as a dictionary where
        keys are the available prefixes and additional information (as returned
        by the `siteinfo/interwikimap` API query).
        """
        interwikis = self.__getattr__("interwikimap")
        return {d["prefix"]: d for d in interwikis}

    @property
    def interlanguagemap(self) -> dict[str, dict[str, str]]:
        """
        Interlanguage prefixes on the wiki, filtered from the general
        :py:attr:`interwikimap <ws.client.API.interwikimap>` property.
        """
        return {
            prefix: info
            for prefix, info in self.interwikimap.items()
            if "local" in info
        }

    @property
    def namespaces(self) -> dict[int, dict[str, str | int]]:
        """
        Namespaces represented as a mapping (dictionary) of namespace IDs to
        dictionaries with information returned by the API.
        """
        namespaces = self.__getattr__("namespaces")
        return {ns["id"]: ns for ns in namespaces.values()}

    @property
    def namespacealiases(self) -> dict[str, dict[str, str | int]]:
        """
        Namespace aliases represented as a mapping (dictionary) of namespace
        names to dictionaries with information returned by the API.
        """
        namespacealiases = self.__getattr__("namespacealiases")
        return {d["*"]: d for d in namespacealiases}

    @property
    def namespacenames(self) -> dict[str, int]:
        """
        Mapping of all valid namespace names, including canonical names and
        aliases, to the corresponding namespace ID.
        """
        names = {
            cast(str, ns["*"]): cast(int, ns["id"]) for ns in self.namespaces.values()
        }
        names.update(
            {
                cast(str, ns["canonical"]): cast(int, ns["id"])
                for ns in self.namespaces.values()
                if "canonical" in ns
            }
        )
        names.update(
            {
                cast(str, ns["*"]): cast(int, ns["id"])
                for ns in self.namespacealiases.values()
            }
        )
        return names

    @property
    def tags(self) -> Generator[dict[str, Any]]:
        """
        A list of all `change tags`_ available on the wiki.

        .. _`change tags`: https://www.mediawiki.org/wiki/Manual:Tags
        """
        # we don't include 'hitcount' in the tgprop, because we wouldn't update it anyway
        # TODO: check that API.list handles tgcontinue in the result
        tags = self._api.list(
            list="tags",
            tgprop="displayname|description|defined|active|source",
            tglimit="max",
        )
        return tags
