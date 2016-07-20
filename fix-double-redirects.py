#! /usr/bin/env python3

import re
import logging

import mwparserfromhell

from ws.client import API
from ws.parser_helpers.title import Title
from ws.interactive import edit_interactive, ask_yesno

logger = logging.getLogger(__name__)

class DoubleRedirects:
    edit_summary = "fix double redirect"

    def __init__(self, api):
        self.api = api
        self.redirects = self.api.site.redirects_map()

    def update_redirect_page(self, page, target):
        title = page["title"]
        text_old = page["revisions"][0]["*"]
        timestamp = page["revisions"][0]["timestamp"]

        if not re.fullmatch(r"#redirect\s*\[\[[^[\]{}|#]+\]\]", text_old, flags=re.MULTILINE | re.IGNORECASE):
            logger.error("Double redirect page '{}' is not empty, so it cannot be fixed automatically.".format(title))
            return

        logger.info("Parsing '{}'...".format(title))
        wikicode = mwparserfromhell.parse(text_old)

        # asserted by the regex match above
        assert(len(wikicode.nodes) == 3)
        assert(isinstance(wikicode.nodes[2], mwparserfromhell.nodes.wikilink.Wikilink))

        wl_target = wikicode.nodes[2]
        wl_target.title = target
        wl_target.text = None
        text_new = str(wikicode)

        if text_old != text_new:
#            edit_interactive(self.api, title, page["pageid"], text_old, text_new, timestamp, self.edit_summary, bot="")
            self.api.edit(title, page["pageid"], text_new, timestamp, self.edit_summary, bot="")

    def findall(self):
        double = {}
        for source, target in self.redirects.items():
            if target in self.redirects:
                double[source] = target
        return double

    def get_last_target(self, source):
        intermediates = set()
        target = self.redirects.get(source)
        source = target
        while source in self.redirects and target not in intermediates:
            target = self.redirects[source]
            intermediates.add(target)
            source = target
        if target in self.redirects:
            logger.error("Failed to resolve last redirect target of '{}': detected infinite loop.".format(source))
            return None
        return target

    def fixall(self):
        double = self.findall()
        if not double:
            logger.info("There are no double redirects.")
            return

        # fetch all revisions at once
        result = self.api.call_api(action="query", titles="|".join(double.keys()), prop="revisions", rvprop="content|timestamp")
        pages = result["pages"]

        for page in pages.values():
            source = page["title"]
            target = self.get_last_target(source)
            if target:
                self.update_redirect_page(page, target)
                

if __name__ == "__main__":
    import ws.config
    api = ws.config.object_from_argparser(API, description="Fix double redirects")
    dr = DoubleRedirects(api)
    dr.fixall()
