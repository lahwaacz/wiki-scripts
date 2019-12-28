#! /usr/bin/env python3

import re
import logging

import mwparserfromhell

from ws.client import API
from ws.interactive import edit_interactive, ask_yesno

logger = logging.getLogger(__name__)

class Recategorize:
    edit_summary = "recategorize to avoid redirect after the old category has been renamed"
    flag_for_deletion_summary = "unused category, flagging for deletion"

    def __init__(self, api):
        self.api = api

    def recategorize_page(self, page, source, target):
        title = page["title"]
        text_old = page["revisions"][0]["slots"]["main"]["*"]
        timestamp = page["revisions"][0]["timestamp"]

        source = self.api.Title(source)
        assert(source.namespace == "Category")

        logger.info("Parsing page [[{}]] ...".format(title))
        wikicode = mwparserfromhell.parse(text_old)
        for wikilink in wikicode.ifilter_wikilinks(recursive=True):
            wl_title = self.api.Title(wikilink.title)
            if wl_title.namespace == "Category" and wl_title.pagename == source.pagename:
                wikilink.title = target
        text_new = str(wikicode)

        if text_old != text_new:
#            edit_interactive(self.api, title, page["pageid"], text_old, text_new, timestamp, self.edit_summary, bot="")
            self.api.edit(title, page["pageid"], text_new, timestamp, self.edit_summary, bot="")

    def flag_for_deletion(self, title):
        _title = self.api.Title(title)
        assert(_title.namespace == "Category")

        result = self.api.call_api(action="query", prop="revisions", rvprop="content|timestamp", rvslots="main", titles=title)
        page = list(result["pages"].values())[0]
        text_old = page["revisions"][0]["slots"]["main"]["*"]
        timestamp = page["revisions"][0]["timestamp"]

        text_new = text_old
        if not re.search("{{deletion\|", text_old, flags=re.IGNORECASE):
            text_new += "\n{{Deletion|unused category}}"
        if text_old != text_new:
            logger.info("Flagging page [[{}]] for deletion.".format(title))
            self.api.edit(title, page["pageid"], text_new, timestamp, self.flag_for_deletion_summary, bot="")

    def recategorize_over_redirect(self, category_namespace=14):
        # FIXME: the source_namespace parameter of redirects.fetch does not work, so we need to do manual filtering
        redirects = self.api.redirects.fetch()
        catredirs = dict((key, value) for key, value in redirects.items() if self.api.Title(key).namespace == "Category")
        for source, target in catredirs.items():
            ans = ask_yesno("Recategorize pages from [[{}]] to [[{}]]?".format(source, target))
            if ans is False:
                continue

            catmembers = self.api.generator(generator="categorymembers", gcmtitle=source, gcmlimit="max", prop="revisions", rvprop="content|timestamp", rvslots="main")
            for page in catmembers:
                # the same page might be yielded multiple times
                if "revisions" in page:
                    self.recategorize_page(page, source, target)
            # check again to see if the category is empty
            catmembers = list(self.api.list(list="categorymembers", cmtitle=source, cmlimit="max"))
            if len(catmembers) == 0:
                self.flag_for_deletion(source)
            else:
                logger.warning("Page [[{}]] is still not empty: {}".format(source, sorted(page["title"] for page in catmembers)))
                input("Press Enter to continue...")
        print("""
Recategorization complete. Before deleting the unused categories, make sure to \
update interlanguage links. The unused categories are still redirects and are \
not listed under Special:UnusedCategories, but they can be found in \
Special:WhatLinksHere/Template:Deletion.
""")

if __name__ == "__main__":
    import ws.config
    api = ws.config.object_from_argparser(API, description="Recategorize pages to avoid redirect after the old category has been renamed")
    r = Recategorize(api)
    r.recategorize_over_redirect()
