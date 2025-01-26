#! /usr/bin/env python3

import itertools
import logging

import mwparserfromhell

import ws.ArchWiki.lang as lang
import ws.utils
from ws.ArchWiki.header import build_header, get_header_parts
from ws.client import APIError
from ws.interactive import edit_interactive

logger = logging.getLogger(__name__)

__all__ = ["Categorization"]

class Categorization:
    """
    Checks if pages are categorized in categories of the same language.
    """

    content_namespaces = [0, 4, 10, 12, 14]
    edit_summary = "fix category, see [[Help:Category#i18n category name]]"

    def __init__(self, api):
        self.api = api

    def find_broken(self):
        def pages_in_namespace(ns):
            return self.api.generator(generator="allpages", gapfilterredir="nonredirects", gapnamespace=ns, gaplimit="max", prop="categories", cllimit="max", clshow="!hidden")

        pages = itertools.chain.from_iterable(pages_in_namespace(ns) for ns in self.content_namespaces)

        needs_fixing = []

        for page in pages:
            langname = lang.detect_language(page["title"])[1]
            if "categories" in page:
                for cat in page["categories"]:
                    # skip root categories for non-English languages
                    if page["title"] == "Category:{}".format(langname) and cat["title"] == "Category:Languages":
                        continue

                    # check language
                    if lang.detect_language(cat["title"])[1] != langname:
                        needs_fixing.append(page["pageid"])

        return needs_fixing

    @staticmethod
    def fix_page(title, text_old):
        langname = lang.detect_language(title)[1]
        wikicode = mwparserfromhell.parse(text_old)
        parent, magics, cats, langlinks = get_header_parts(wikicode, remove_from_parent=True)

        for cat in cats:
            # get_header_parts returns list of wikicode objects, each with one node
            cat = cat.nodes[0]

            pure, ln = lang.detect_language(str(cat.title))
            if ln != langname:
                cat.title = lang.format_title(pure, langname)

        build_header(wikicode, parent, magics, cats, langlinks)
        return wikicode

    def fix_allpages(self):
        pageids = self.find_broken()
        if not pageids:
            logger.info("All pages are categorized under correct language.")
            return

        for chunk in ws.utils.iter_chunks(pageids, self.api.max_ids_per_query):
            pageids = "|".join(str(pageid) for pageid in chunk)
            result = self.api.call_api(action="query", pageids=pageids, prop="revisions", rvprop="content|timestamp", rvslots="main")
            pages = result["pages"]
            for page in pages.values():
                logger.info("Fixing language of categories on page [[{}]]...".format(page["title"]))

                timestamp = page["revisions"][0]["timestamp"]
                text_old = page["revisions"][0]["slots"]["main"]["*"]
                text_new = self.fix_page(page["title"], text_old)

                if text_old != text_new:
                    try:
                        edit_interactive(self.api, page["title"], page["pageid"], text_old, text_new, timestamp, self.edit_summary, bot="")
#                        self.api.edit(page["title"], page["pageid"], text_new, timestamp, self.edit_summary, bot="")
                    except APIError:
                        pass
