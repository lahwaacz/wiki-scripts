#! /usr/bin/env python3

import logging

import mwparserfromhell

from .selects.namespaces import get_namespaces
from ..parser_helpers.template_expansion import expand_templates

logger = logging.getLogger(__name__)

class ParserCache:
    def __init__(self, db):
        self.db = db

    def _parse_page(self, pageid, title, content):
        # TODO: drop all entries corresponding to this page
        logger.info("_parse_page({}, {})".format(pageid, title))

        # set of all pages transcluded on the current page
        # (will be filled by the content_getter function)
        transclusions = set()

        def content_getter(title):
            nonlocal transclusions
            transclusions.add(title)
            pages_gen = self.db.query(titles={title}, prop="latestrevisions", rvprop="content")
            page = next(pages_gen)
            if "revisions" in page:
                if "*" in page["revisions"][0]:
                    return page["revisions"][0]["*"]
                else:
                    logger.error("ParserCache: no latest revision found for page [[{}]]".format(page["title"]))
                    raise ValueError
            else:
                # no revision => page does not exist
                logger.warn("ParserCache: page not found: {{" + title + "}}")
                raise ValueError

        content = mwparserfromhell.parse(content)
        expand_templates(title, content, content_getter)

#        print(content)
        print("transclusions:", transclusions)

    def update(self):
        # TODO: determine which pages should be updated - record a timestamp in the ws_sync table (just like grabbers), compare it to page_touched
        namespaces = get_namespaces(self.db)
        for ns in namespaces.keys():
            if ns < 0:
                continue
            for page in self.db.query(generator="allpages", gapnamespace=ns, prop="latestrevisions", rvprop="content"):
                if "*" in page["revisions"][0]:
                    self._parse_page(page["pageid"], page["title"], page["revisions"][0]["*"])
                else:
                    logger.error("ParserCache: no latest revision found for page [[{}]]".format(page["title"]))
