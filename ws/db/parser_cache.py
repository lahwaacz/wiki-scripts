#! /usr/bin/env python3

import logging

import mwparserfromhell

from .selects.namespaces import get_namespaces
from ..parser_helpers.template_expansion import expand_templates

logger = logging.getLogger(__name__)

# TODO: generalize SQL query execution like in ws.db.grabbers

class ParserCache:
    def __init__(self, db):
        self.db = db

    def _drop_cache_for_page(self, conn, pageid, title):
        conn.execute(self.db.pagelinks.delete().where(self.db.pagelinks.c.pl_from == pageid))
        conn.execute(self.db.templatelinks.delete().where(self.db.templatelinks.c.tl_from == pageid))
        conn.execute(self.db.imagelinks.delete().where(self.db.imagelinks.c.il_from == pageid))
        conn.execute(self.db.categorylinks.delete().where(self.db.categorylinks.c.cl_from == pageid))
        conn.execute(self.db.langlinks.delete().where(self.db.langlinks.c.ll_from == pageid))
        conn.execute(self.db.iwlinks.delete().where(self.db.iwlinks.c.iwl_from == pageid))
        conn.execute(self.db.externallinks.delete().where(self.db.externallinks.c.el_from == pageid))
        conn.execute(self.db.redirect.delete().where(self.db.redirect.c.rd_from == pageid))

        # TODO: shouldn't category have a foreign key to page.page_id?
        title = self.db.Title(title)
        conn.execute(self.db.category.delete().where(self.db.category.c.cat_title == title.dbtitle(expected_ns=14)))

    def _insert_templatelinks(self, conn, pageid, transclusions):
        db_entries = []
        for t in transclusions:
            title = self.db.Title(t)
            entry = {
                "tl_from": pageid,
                "tl_namespace": title.namespacenumber,
                "tl_title": title.dbtitle(),
            }
            db_entries.append(entry)

        if db_entries:
            conn.execute(self.db.templatelinks.insert(), db_entries)

    def _parse_page(self, conn, pageid, title, content):
        logger.info("_parse_page({}, {})".format(pageid, title))

        # drop all entries corresponding to this page
        self._drop_cache_for_page(conn, pageid, title)

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

        # templatelinks can be updated right away
        self._insert_templatelinks(conn, pageid, transclusions)

#        print(content)

    def update(self):
        # TODO: determine which pages should be updated - record a timestamp in the ws_sync table (just like grabbers), compare it to page_touched
        namespaces = get_namespaces(self.db)
        for ns in namespaces.keys():
            if ns < 0:
                continue
            for page in self.db.query(generator="allpages", gapnamespace=ns, prop="latestrevisions", rvprop="content"):
                # one transaction per page
                with self.db.engine.begin() as conn:
                    if "*" in page["revisions"][0]:
                        self._parse_page(conn, page["pageid"], page["title"], page["revisions"][0]["*"])
                    else:
                        logger.error("ParserCache: no latest revision found for page [[{}]]".format(page["title"]))
