#! /usr/bin/env python3

import logging
from typing import Any

import mwparserfromhell

from ws.client import API
from ws.parser_helpers.wikicode import is_redirect

logger = logging.getLogger(__name__)


class DoubleRedirects:
    edit_summary = "fix double redirect"

    def __init__(self, api: API):
        self.api = api

    def update_redirect_page(self, page: dict[str, Any], target: str) -> None:
        title = page["title"]
        text_old = page["revisions"][0]["slots"]["main"]["*"]
        timestamp = page["revisions"][0]["timestamp"]

        if not is_redirect(text_old, full_match=True):
            logger.error(f"Double redirect page '{title}' is not empty, so it cannot be fixed automatically.")
            return

        logger.info(f"Parsing '{title}'...")
        wikicode = mwparserfromhell.parse(text_old)

        # asserted by the regex match above
        assert len(wikicode.nodes) == 3
        assert isinstance(wikicode.nodes[2], mwparserfromhell.nodes.wikilink.Wikilink)

        wl_target = wikicode.nodes[2]
        wl_target.title = target
        wl_target.text = None
        text_new = str(wikicode)

        # also add Category:Archive to the redirect
        if target.startswith("ArchWiki:Archive"):
            text_new = text_new.rstrip() + "\n[[Category:Archive]]"

        if text_old != text_new:
            self.api.edit(title, page["pageid"], text_new, timestamp, self.edit_summary, bot="")

    def findall(self) -> dict[str, str]:
        double: dict[str, str] = {}
        for source, target in self.api.redirects.map.items():
            target = target.split("#", maxsplit=1)[0]
            if target in self.api.redirects.map:
                double[source] = target
        return double

    def fixall(self) -> None:
        double = self.findall()
        if not double:
            logger.info("There are no double redirects.")
            return

        # fetch all revisions at once
        result = self.api.call_api(action="query", titles="|".join(double.keys()), prop="revisions", rvprop="content|timestamp", rvslots="main")
        pages = result["pages"]

        for page in pages.values():
            source = page["title"]
            target = self.api.redirects.resolve(source)
            if target:
                self.update_redirect_page(page, target)


if __name__ == "__main__":
    import ws.config

    api = ws.config.object_from_argparser(API, description="Fix double redirects")
    dr = DoubleRedirects(api)
    dr.fixall()
