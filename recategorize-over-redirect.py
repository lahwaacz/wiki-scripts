#! /usr/bin/env python3

import os
import mwparserfromhell

from ws.core import API
from ws.parser_helpers import canonicalize
from ws.interactive import edit_interactive, ask_yesno

class Recategorize:
    edit_summary = "recategorize to avoid redirect (https://github.com/lahwaacz/wiki-scripts/blob/master/recategorize-over-redirect.py)"
    flag_for_deletion_summary = "unused category, flagging for deletion (https://github.com/lahwaacz/wiki-scripts/blob/master/recategorize-over-redirect.py)"

    def __init__(self, api):
        self.api = api

    def recategorize_page(self, page, source, target):
        title = page["title"]
        text_old = page["revisions"][0]["*"]
        timestamp = page["revisions"][0]["timestamp"]

        print("Parsing '{}'...".format(title))
        wikicode = mwparserfromhell.parse(text_old)
        for wikilink in wikicode.ifilter_wikilinks(recursive=True):
            if canonicalize(wikilink.title) == source:
                wikilink.title = target
        text_new = str(wikicode)

        if text_old != text_new:
            print("Editing '{}'".format(title))
#            edit_interactive(self.api, page["pageid"], text_old, text_new, timestamp, self.edit_summary, bot="")
            api.edit(page["pageid"], text_new, timestamp, self.edit_summary, bot="")

    def flag_for_deletion(self, title):
        namespace, pure = self.api.detect_namespace(title)
        assert(namespace == "Category")

        result = self.api.call(action="query", prop="revisions", rvprop="content|timestamp", titles=title)
        page = list(result["pages"].values())[0]
        text_old = page["revisions"][0]["*"]
        timestamp = page["revisions"][0]["timestamp"]

        text_new = "{{Deletion|unused category}}"
        if text_old != text_new:
            print("Flagging for deletion: '{}'".format(title))
            api.edit(page["pageid"], text_new, timestamp, self.flag_for_deletion_summary, bot="")

    def recategorize_over_redirect(self, category_namespace=14):
        # FIXME: the source_namespace parameter of redirects_map does not work,
        #        so we need to do manual filtering
        redirects = self.api.redirects_map()
        catredirs = dict((key, value) for key, value in redirects.items() if api.detect_namespace(key)[0] == "Category")
        for source, target in catredirs.items():
            ans = ask_yesno("Recategorize pages from '{}' to '{}'?".format(source, target))
            if ans is False:
                continue

            catmembers = self.api.generator(generator="categorymembers", gcmtitle=source, gcmlimit="max", prop="revisions", rvprop="content|timestamp")
            for page in catmembers:
                # the same page might be yielded multiple times
                if "revisions" in page:
                    self.recategorize_page(page, source, target)
            # check again to see if the category is empty
            catmembers = list(self.api.list(list="categorymembers", cmtitle=source, cmlimit="max"))
            if len(catmembers) == 0:
                self.flag_for_deletion(source)
            else:
                print("Warning: '{}' is still not empty:".format(source), sorted(page["title"] for page in catmembers))
                input("Press Enter to continue...")

if __name__ == "__main__":
    api_url = "https://wiki.archlinux.org/api.php"
    cookie_path = os.path.expanduser("~/.cache/ArchWiki.bot.cookie")

    api = API(api_url, cookie_file=cookie_path, ssl_verify=True)

    r = Recategorize(api)
    r.recategorize_over_redirect()
