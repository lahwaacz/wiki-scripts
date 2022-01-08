#! /usr/bin/env python3

import itertools
import logging

import mwparserfromhell

from ws.client import APIError
import ws.utils
from ws.interactive import edit_interactive
from ws.ArchWiki.header import get_header_parts, build_header

logger = logging.getLogger(__name__)

__all__ = ["Decategorization"]

class Decategorization:
    """
    Checks if pages in the User namespace and talk pages are not categorized.
    """

    uncat_namespaces = [1, 2, 3, 5, 7, 9, 11, 13, 15]

    def __init__(self, api):
        self.api = api

    def find_categorized(self):
        def pages_in_namespace(ns):
            return self.api.generator(generator="allpages", gapfilterredir="nonredirects", gapnamespace=ns, gaplimit="max", prop="categories", cllimit="max", clshow="!hidden")

        pages = itertools.chain.from_iterable(pages_in_namespace(ns) for ns in self.uncat_namespaces)

        categorized = []

        for page in pages:
            if "categories" in page:
                for cat in page["categories"]:
                    categorized.append(page["pageid"])

        return categorized

    @staticmethod
    def decategorize(title, text_old):
        wikicode = mwparserfromhell.parse(text_old)
        parent, magics, cats, langlinks = get_header_parts(wikicode, remove_from_parent=True)
        build_header(wikicode, parent, magics, [], langlinks)
        return wikicode

    def fix_allpages(self):
        pageids = self.find_categorized()
        if not pageids:
            logger.info("All pages are categorized under correct language.")
            return

        for chunk in ws.utils.iter_chunks(pageids, self.api.max_ids_per_query):
            pageids = "|".join(str(pageid) for pageid in chunk)
            result = self.api.call_api(action="query", pageids=pageids, prop="revisions", rvprop="content|timestamp", rvslots="main")
            pages = result["pages"]
            for page in pages.values():
                logger.info("Decategorizing page [[{}]]...".format(page["title"]))

                timestamp = page["revisions"][0]["timestamp"]
                text_old = page["revisions"][0]["slots"]["main"]["*"]
                text_new = self.decategorize(page["title"], text_old)

                if text_old != text_new:
                    title = self.api.Title(page["title"])
                    if title.namespace == "User":
                        edit_summary = "user pages shall not be categorized, see [[Help:Style#User pages]]"
                    else:
                        edit_summary = "talk pages should not be categorized"
                    try:
                        edit_interactive(self.api, page["title"], page["pageid"], text_old, text_new, timestamp, edit_summary, bot="")
#                        self.api.edit(page["title"], page["pageid"], text_new, timestamp, edit_summary, bot="")
                    except APIError:
                        pass
                else:
                    logger.error("Failed to decategorize page [[{}]]".format(page["title"]))
