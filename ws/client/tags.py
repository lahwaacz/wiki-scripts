from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .api import API


class Tags:
    """
    An interface for MediaWiki's `change tags`_.

    .. _`change tags`: https://www.mediawiki.org/wiki/Manual:Tags
    """

    def __init__(self, api: "API"):
        self.api = api

        self._tags = list(
            self.api.list(list="tags", tglimit="max", tgprop="source|active")
        )

    @property
    def all(self) -> set[str]:
        """
        Names of all tags present on the wiki.
        """
        return {tag["name"] for tag in self._tags}

    @property
    def active(self) -> set[str]:
        """
        Names of active tags.
        """
        return {tag["name"] for tag in self._tags if "active" in tag}

    @property
    def manual(self) -> set[str]:
        """
        Names of tags defined manually.
        """
        return {tag["name"] for tag in self._tags if "manual" in tag["source"]}

    @property
    def extension(self) -> set[str]:
        """
        Names of tags defined by extensions.
        """
        return {tag["name"] for tag in self._tags if "extension" in tag["source"]}

    @property
    def applicable(self) -> set[str]:
        """
        Names of active tags that may be applied by users and bots.
        """
        return self.active & self.manual
