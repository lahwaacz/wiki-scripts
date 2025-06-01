# TODO:
#   take the final title from "displaytitle" property (available from API) (would be necessary to check if it is valid)

import itertools
import logging
import re
from typing import Any, Generator, Iterable, Sequence

import mwparserfromhell
from mwparserfromhell.wikicode import Wikicode

import ws.ArchWiki.header as header
import ws.ArchWiki.lang as lang
import ws.utils
from ws.client import API, APIError
from ws.interactive import ask_yesno
from ws.parser_helpers.title import canonicalize

logger = logging.getLogger(__name__)

__all__ = ["InterlanguageLinks"]


class InterlanguageLinks:
    """
    Update interlanguage links on ArchWiki based on the following algorithm:

     1. Fetch list of all pages with prop=langlinks to be able to build a
        langlink graph (separate from the content dict for quick searching).
     2. Group pages into families based on their title, which is the primary key
        to denote a family. The grouping is case-insensitive and includes even
        pages without any interlanguage links. The family name corresponds to
        the only English page in the family (or when not present, to the English
        base of the localized title).
     3. For every page on the wiki:

        a) Determine the family of the page.
        b) Assemble a set of pages in the family. This is done by first
           including the pages in the group from step 2., then pulling any
           internal langlinks from the pages in the set (in unspecified order),
           and finally based on the presence of an English page in the family:

           - If there is an English page directly in the group from step 2. or
             if other pages link to an English page whose group can be merged
             with the current group without causing a conflict, its external
             langlinks are pulled in. As a result, external langlinks removed
             from the English page are assumed to be invalid and removed also
             from other pages in the family. For consistency, also internal
             langlinks are pulled from the English page.
           - If the pulling from an English page was not done, external
             langlinks are pulled from the other pages (in unspecified order),
             which completes the previous inclusion of internal langlinks.

        c) Check if it is necessary to update the page by comparing the new set
           of langlinks for a page (i.e. ``family.titles - {title}``) with the
           old set obtained from the wiki's API. If an update is needed:

           - Fetch content of the page.
           - Update the langlinks of the page.
           - If there is a difference, save the page.
    """

    content_namespaces = [0, 4, 10, 12, 14]
    edit_summary = "update interlanguage links"

    def __init__(self, api: API):
        self.api = api

        self.families: dict[str, list[dict[str, Any]]] = {}
        self.family_index: dict[str, str] = {}

    def _get_allpages(self) -> list[dict[str, Any]]:
        logger.info("Fetching langlinks property of all pages...")
        allpages: list[dict[str, Any]] = []
        # not necessary to wrap in each iteration since lists are mutable
        wrapped_titles = ws.utils.ListOfDictsAttrWrapper(allpages, "title")

        for ns in self.content_namespaces:
            g = self.api.generator(
                generator="allpages",
                gapfilterredir="nonredirects",
                gapnamespace=ns,
                gaplimit="max",
                prop="langlinks",
                lllimit="max",
            )
            for page in g:
                # the same page may be yielded multiple times with different pieces
                # of the information, hence the ws.utils.dmerge
                try:
                    db_page = ws.utils.bisect_find(
                        allpages, page["title"], index_list=wrapped_titles
                    )
                    ws.utils.dmerge(page, db_page)
                except IndexError:
                    ws.utils.bisect_insert_or_replace(
                        allpages,
                        page["title"],
                        data_element=page,
                        index_list=wrapped_titles,
                    )

        # sort by title
        allpages.sort(key=lambda page: page["title"])
        return allpages

    @staticmethod
    def _group_into_families(
        pages: Iterable[dict[str, Any]], case_sensitive: bool = False
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Takes list of pages and groups them based on their title. Returns a
        mapping of `family_key` to `family_pages`, where `family_key` is the
        base title without the language suffix (e.g. "Some title" for
        "Some title (Česky)") and `family_pages` is a list of pages belonging
        to the family (have the same `family_key`).
        """

        # interlanguage links are not valid for all languages, the invalid
        # need to be dropped now
        def _valid_interlanguage_pages(
            pages: Iterable[dict[str, Any]]
        ) -> Generator[dict[str, Any]]:
            for page in pages:
                langname = lang.detect_language(page["title"])[1]
                tag = lang.tag_for_langname(langname)
                if lang.is_interlanguage_tag(tag):
                    yield page

        def _family_key(page):
            key = lang.detect_language(page["title"])[0]
            if case_sensitive is False:
                key = key.lower()
            return key

        pages = sorted(pages, key=_family_key)
        families_groups = itertools.groupby(
            _valid_interlanguage_pages(pages), key=_family_key
        )

        families = {}
        for family, pages in families_groups:
            pages = list(pages)
            tags = set(
                lang.tag_for_langname(lang.detect_language(page["title"])[1])
                for page in pages
            )
            if len(tags) == len(pages):
                families[family] = pages
            elif case_sensitive is False:
                # sometimes case-insensitive matching is not enough, e.g. [[fish]] is
                # not [[FiSH]] (and neither is redirect)
                families.update(
                    InterlanguageLinks._group_into_families(pages, case_sensitive=True)
                )
            else:
                # this should never happen
                raise Exception
        return families

    @ws.utils.LazyProperty
    def allpages(self) -> list[dict[str, Any]]:
        allpages = self._get_allpages()
        self.families = self._group_into_families(allpages)

        # create inverse mapping for fast searching
        self.family_index = {}
        for family, pages in self.families.items():
            for page in pages:
                self.family_index[page["title"]] = family

        return allpages

    @property
    def wrapped_titles(self) -> ws.utils.ListOfDictsAttrWrapper:
        return ws.utils.ListOfDictsAttrWrapper(self.allpages, "title")

    @staticmethod
    # check if interlanguage links are supported for the language of the given title
    def _is_valid_interlanguage(full_title: str) -> bool:
        return lang.is_interlanguage_tag(
            lang.tag_for_langname(lang.detect_language(full_title)[1])
        )

    # check if given (tag, title) form a valid internal langlink
    def _is_valid_internal(self, tag: str, title: str) -> bool:
        if not lang.is_internal_tag(tag):
            return False
        if "/" in title:
            full_title = lang.format_title(
                title, lang.langname_for_tag(tag), augment_all_subpage_parts=False
            )
            if full_title in self.wrapped_titles:
                return True
        full_title = lang.format_title(title, lang.langname_for_tag(tag))
        return full_title in self.wrapped_titles

    def _title_from_langlink(self, langlink: dict[str, str]) -> str:
        langname = lang.langname_for_tag(langlink["lang"])
        title = lang.format_title(langlink["*"], langname)
        if lang.is_internal_tag(langlink["lang"]):
            title = canonicalize(title)
            # resolve redirects
            resolved = self.api.redirects.resolve(title)
            if resolved is not None:
                title = resolved.split("#", maxsplit=1)[0]
        return title

    def titles_in_family(self, master_title: str) -> tuple[list[str], list[str]]:
        """
        Get the titles in the family corresponding to ``master_title``.

        :param str master_title: a page title (does not have to be English page)
        :returns: a ``(titles, tags)`` tuple, where ``titles`` is the set of titles
                  in the family (including ``title``) and ``tags`` is the set of
                  corresponding language tags
        """
        family = self.family_index[master_title]
        family_pages = self.families[family]
        # we don't need the full title any more
        master_title, master_lang = lang.detect_language(master_title)
        master_tag = lang.tag_for_langname(master_lang)

        tags = []
        titles = []

        # populate titles/tags with the already present pages
        for page in family_pages:
            title, langname = lang.detect_language(page["title"])
            tag = lang.tag_for_langname(langname)
            if tag not in tags:
                tags.append(tag)
                titles.append(title)
        had_english_early = "en" in tags

        def _pull_from_page(page, condition=lambda tag, title: True):
            # default to empty tuple
            for langlink in page.get("langlinks", ()):
                tag = langlink["lang"]
                # conversion back and forth is necessary to resolve redirect
                full_title = self._title_from_langlink(langlink)
                title, langname = lang.detect_language(full_title)
                # TODO: check if the resulting tag is equal to the original?
                #                tag = lang.tag_for_langname(langname)
                if tag not in tags and condition(tag, title):
                    tags.append(tag)
                    titles.append(title)

        # Pull in internal langlinks from any page. This will pull in English page
        # if there is any.
        for page in family_pages:
            _pull_from_page(
                page, condition=lambda tag, title: self._is_valid_internal(tag, title)
            )

        # Make sure that external langlinks are pulled in only from the English page
        # when appropriate. For consistency, pull in also internal langlinks from the
        # English page.
        _pulled_from_english = False
        if "en" in tags:
            en_title = titles[tags.index("en")]
            en_page = ws.utils.bisect_find(
                self.allpages, en_title, index_list=self.wrapped_titles
            )
            # If the English page is present from the beginning, pull its langlinks.
            # This will take priority over other pages in the family.
            if master_tag == "en" or had_english_early:
                _pull_from_page(
                    en_page,
                    condition=lambda tag, title: lang.is_external_tag(tag)
                    or self._is_valid_internal(tag, title),
                )
                _pulled_from_english = True
            else:
                # Otherwise check if the family of the English page is the same as
                # this one or if it does not contain master_tag. This will effectively
                # merge the families.
                en_tags, en_titles = self.titles_in_family(en_title)
                if master_title in en_titles or master_tag not in en_tags:
                    _pull_from_page(
                        en_page,
                        condition=lambda tag, title: lang.is_external_tag(tag)
                        or self._is_valid_internal(tag, title),
                    )
                    _pulled_from_english = True

        if not _pulled_from_english:
            # Pull in external langlinks from any page. This completes the
            # inclusion in case pulling from English page was not done.
            for page in family_pages:
                _pull_from_page(
                    page, condition=lambda tag, title: lang.is_external_tag(tag)
                )

        assert master_tag in tags
        assert master_title in titles
        assert len(tags) == len(titles)

        return tags, titles

    def get_langlinks(self, full_title: str) -> list[tuple[str, str]]:
        """
        Uses :py:meth:`self.titles_in_family` to get the titles of all pages in
        the family, removes the link to the passed title and sorts the list by
        the language subtag.

        :returns: a list of ``(tag, title)`` tuples
        """
        # get all titles in the family
        tags, titles = self.titles_in_family(full_title)
        langlinks = set(zip(tags, titles))

        title, langname = lang.detect_language(full_title)
        tag = lang.tag_for_langname(langname)

        # remove links to ArchWiki:Archive and translations
        if title != "ArchWiki:Archive":
            for _tag, _title in list(langlinks):
                if _title == "ArchWiki:Archive":
                    langlinks.remove((_tag, _title))

        # remove title of the page to be updated
        langlinks.remove((tag, title))

        # transform to list, sort by the language tag
        sorted_langlinks = sorted(langlinks, key=lambda t: t[0])

        # conversion back-and-forth is necessary to add the "(Language)" suffix into all subpage parts
        new_langlinks = []
        for tag, title in sorted_langlinks:
            new_title = lang.format_title(title, lang.langname_for_tag(tag))
            # do it only when the new_title exists, otherwise the title without "(Language)" in
            # all subpage parts is still valid as per Help:i18n
            if self._page_exists(new_title):
                title = lang.detect_language(new_title, strip_all_subpage_parts=False)[
                    0
                ]
            new_langlinks.append((tag, title))

        return new_langlinks

    @staticmethod
    def update_page(
        title: str,
        text: str,
        langlinks: list[tuple[str, str]],
        weak_update: bool = True,
    ) -> Wikicode | None:
        """
        :param str title: title of the page
        :param str text: wikitext of the page
        :param langlinks: a sorted list of ``(tag, title)`` tuples as obtained
                          from :py:meth:`self.get_langlinks`
        :param weak_update:
            When ``True``, the langlinks present on the page are mixed with those
            suggested by ``family_titles``. This is necessary only when there are
            multiple "intersecting" families, in which case the intersection should
            be preserved and solved manually. This is reported in _merge_families.
        :returns: updated wikicode
        """
        # temporarily skip main pages until the behavior switches
        # (__NOTOC__ etc.) can be parsed by mwparserfromhell
        # NOTE: handling whitespace right will be hard: https://wiki.archlinux.org/index.php?title=Main_page&diff=383144&oldid=382787
        if re.search("__NOTOC__|__NOEDITSECTION__", text):
            logger.warning(f"Skipping page '{title}' (contains behavior switch(es))")
            return None

        # format langlinks, in the prefix form
        # (e.g. "cs:Some title" for title="Some title" and tag="cs")
        full_langlinks: Sequence[str | Wikicode]
        full_langlinks = [f"[[{tag}:{title}]]" for tag, title in langlinks]

        logger.info(f"Parsing page [[{title}]] ...")
        wikicode = mwparserfromhell.parse(text)
        if weak_update is True:
            parent, magics, cats, full_langlinks = header.get_header_parts(
                wikicode, langlinks=full_langlinks, remove_from_parent=True
            )
        else:
            # drop the extracted langlinks
            parent, magics, cats, _ = header.get_header_parts(
                wikicode, remove_from_parent=True
            )
        header.build_header(wikicode, parent, magics, cats, full_langlinks)
        return wikicode

    @staticmethod
    def _needs_update(
        page: dict[str, Any], langlinks_new: list[tuple[str, str]]
    ) -> bool:
        langlinks_old = []
        try:
            for langlink in page["langlinks"]:
                langlinks_old.append((langlink["lang"], langlink["*"]))
        except KeyError:
            pass
        return set(langlinks_new) != set(langlinks_old)

    def update_allpages(self) -> None:
        # always start from scratch
        del self.allpages

        def _updates_gen(pages_gen):
            for page in pages_gen:
                title = page["title"]
                # unsupported languages need to be skipped now
                if not self._is_valid_interlanguage(title):
                    logger.warning(f"Skipping page '{title}' (unsupported language)")
                    continue
                langlinks = self.get_langlinks(title)
                if self._needs_update(page, langlinks):
                    yield page, langlinks

        for chunk in ws.utils.iter_chunks(
            _updates_gen(self.allpages), self.api.max_ids_per_query
        ):
            pages_props, pages_langlinks = zip(*list(chunk))
            pageids = [page["pageid"] for page in pages_props]
            result: dict[str, Any] = {}
            for chunk in self.api.call_api_autoiter_ids(
                action="query",
                pageids=pageids,
                prop="revisions",
                rvprop="content|timestamp",
                rvslots="main",
            ):
                ws.utils.dmerge(chunk, result)
            pages = result["pages"]

            for page, langlinks in zip(pages_props, pages_langlinks):
                # substitute the dictionary with langlinks with the dictionary with content
                page = pages[str(page["pageid"])]

                timestamp = page["revisions"][0]["timestamp"]
                text_old = page["revisions"][0]["slots"]["main"]["*"]
                try:
                    text_new = self.update_page(
                        page["title"], text_old, langlinks, weak_update=False
                    )
                except header.HeaderError:
                    logger.error(
                        "Error: failed to extract header elements. Please investigate."
                    )
                    continue
                if text_new is None:
                    continue

                if text_old != text_new:
                    try:
                        # edit_interactive(self.api, page["title"], page["pageid"], text_old, text_new, timestamp, self.edit_summary, bot="")
                        self.api.edit(
                            page["title"],
                            page["pageid"],
                            text_new,
                            timestamp,
                            self.edit_summary,
                            bot="",
                        )
                    except APIError:
                        pass

    def find_orphans(self) -> list[str]:
        """
        Returns list of pages that are alone in their families.
        """
        orphans = []
        for page in self.allpages:
            title = page["title"]
            # unsupported languages need to be skipped now
            if not self._is_valid_interlanguage(title):
                continue
            langlinks = self.get_langlinks(title)
            if (
                lang.detect_language(title)[1] != lang.get_local_language()
                and len(langlinks) == 0
            ):
                orphans.append(title)
        return orphans

    def _page_exists(self, title: str) -> bool:
        # self.allpages does not include redirects, but that's fine...
        return canonicalize(title) in set(page["title"] for page in self.allpages)

    def rename_non_english(self) -> None:
        del self.allpages

        # FIXME: starting with English pages is not very good:
        # - some pages are omitted (e.g. when two pages link to the same English page, at least warning should be printed)
        # - it suggests to move e.g. Xfce (Česky) to Xfwm (Česky) because multiple English pages link to it
        # Therefore we limit it only to categories...
        for page in self.allpages:
            title = page["title"]
            if lang.detect_language(title)[1] == "English" and title.startswith(
                "Category:"
            ):
                langlinks = self.get_langlinks(title)
                for tag, localized_title in langlinks:
                    logger.info(f"Checking [[{tag}:{localized_title}]] for renaming...")
                    if lang.is_internal_tag(tag) and localized_title != title:
                        source = f"{localized_title} ({lang.langname_for_tag(tag)})"
                        target = f"{title} ({lang.langname_for_tag(tag)})"
                        if self._page_exists(target):
                            logger.warning(
                                f"Cannot move page [[{source}]] to [[{target}]]: target page already exists"
                            )
                        else:
                            # interactive mode is necessary because this assumes that all English pages are named correctly
                            ans = ask_yesno(f"Move page [[{source}]] to [[{target}]]?")
                            if ans is True:
                                summary = "comply with [[Help:I18n#Page titles]] and match the title of the English page"
                                self.api.move(source, target, summary)
