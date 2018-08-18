#! /usr/bin/env python3

import logging

import mwparserfromhell

from .selects.namespaces import get_namespaces
from ..parser_helpers.template_expansion import expand_templates

# TODO: generalize or make the language tags configurable
from ws.ArchWiki.lang import get_language_tags

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

        # TODO: drop cache for all pages transcluding this page

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

    def _insert_pagelinks(self, conn, pageid, pagelinks):
        db_entries = []
        for title in pagelinks:
            entry = {
                "pl_from": pageid,
                "pl_namespace": title.namespacenumber,
                "pl_title": title.pagename,
            }
            db_entries.append(entry)

        # drop duplicates
        db_entries = list({ (v["pl_from"], v["pl_namespace"], v["pl_title"] ):v for v in db_entries}.values())

        if db_entries:
            conn.execute(self.db.pagelinks.insert(), db_entries)

    def _insert_imagelinks(self, conn, pageid, imagelinks):
        db_entries = []
        for title in imagelinks:
            entry = {
                "il_from": pageid,
                "il_to": title.pagename,
            }
            db_entries.append(entry)

        # drop duplicates
        db_entries = list({ (v["il_from"], v["il_to"] ):v for v in db_entries}.values())

        if db_entries:
            conn.execute(self.db.imagelinks.insert(), db_entries)

    def _insert_categorylinks(self, conn, pageid, from_title, categorylinks):
        db_entries = []
        for title, prefix in categorylinks:
            sortkey = from_title.pagename.upper()
            if prefix:
                sortkey = prefix.upper() + "\n" + sortkey

            cl_type = "page"
            if from_title.namespacenumber == 6:
                cl_type = "file"
            if from_title.namespacenumber == 14:
                cl_type = "subcat"

            entry = {
                "cl_from": pageid,
                "cl_to": title.pagename,
                "cl_sortkey": sortkey,
                "cl_sortkey_prefix": prefix,
                # TODO: depends on $wgCategoryCollation: https://www.mediawiki.org/wiki/Manual:$wgCategoryCollation
                "cl_collation": "uppercase",
                "cl_type": cl_type,
            }
            db_entries.append(entry)

        # drop duplicates
        db_entries = list({ (v["cl_from"], v["cl_to"] ):v for v in db_entries}.values())

        if db_entries:
            conn.execute(self.db.categorylinks.insert(), db_entries)

    def _insert_langlinks(self, conn, pageid, langlinks):
        db_entries = []
        for title in langlinks:
            entry = {
                "ll_from": pageid,
                "ll_lang": title.iwprefix.lower(),
                "ll_title": "{}:{}".format(title.namespace, title.pagename) if title.namespace else title.pagename
            }
            db_entries.append(entry)

        # drop duplicates
        db_entries = list({ (v["ll_from"], v["ll_lang"], v["ll_title"] ):v for v in db_entries}.values())

        if db_entries:
            conn.execute(self.db.langlinks.insert(), db_entries)

    def _insert_iwlinks(self, conn, pageid, iwlinks):
        db_entries = []
        for title in iwlinks:
            entry = {
                "iwl_from": pageid,
                "iwl_prefix": title.iwprefix.lower(),
                "iwl_title": "{}:{}".format(title.namespace, title.pagename) if title.namespace else title.pagename
            }
            db_entries.append(entry)

        # drop duplicates
        db_entries = list({ (v["iwl_from"], v["iwl_prefix"], v["iwl_title"] ):v for v in db_entries}.values())

        if db_entries:
            conn.execute(self.db.iwlinks.insert(), db_entries)

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

        # before other parsing, handle the transclusion tags
        for tag in content.ifilter_tags(recursive=True):
            # drop all <includeonly> tags and everything inside
            if tag.tag == "includeonly":
                try:
                    content.remove(tag)
                except ValueError:
                    # this may happen for nested tags which were previously removed/replaced
                    pass
            # drop <noinclude> and <onlyinclude> tags, but nothing outside or inside
            elif tag.tag == "noinclude" or tag.tag == "onlyinclude":
                try:
                    content.replace(tag, tag.contents)
                except ValueError:
                    # this may happen for nested tags which were previously removed/replaced
                    pass

        pagelinks = []
        imagelinks = []
        categorylinks = []
        langlinks = []
        iwlinks = []

        # classify all wikilinks
        for wl in content.ifilter_wikilinks(recursive=True):
            target = self.db.Title(wl.title)
            if target.iwprefix:
                if target.iwprefix in get_language_tags():
                    langlinks.append(target)
                else:
                    iwlinks.append(target)
            elif target.namespacenumber == -2:
                # MediaWiki treats all links to the Media: namespace as imagelinks
                imagelinks.append(target)
            # TODO: handling of the leading colon should be done in the Title class
            elif target.namespacenumber == 6 and not str(wl.title).strip().startswith(":"):
                imagelinks.append(target)
            # TODO: handling of the leading colon should be done in the Title class
            elif target.namespacenumber == 14 and not str(wl.title).strip().startswith(":"):
                # MW incompatibility: category links for automatic categories like
                # "Pages with broken file links" are not supported
                categorylinks.append( (target, str(wl.text) if wl.text else "") )
            else:
                # MediaWiki does not track links to the Special: and Media: namespaces
                if target.namespacenumber >= 0:
                    pagelinks.append(target)

        self._insert_pagelinks(conn, pageid, pagelinks)
        self._insert_iwlinks(conn, pageid, iwlinks)
        self._insert_categorylinks(conn, pageid, self.db.Title(title), categorylinks)
        self._insert_langlinks(conn, pageid, langlinks)
        self._insert_imagelinks(conn, pageid, imagelinks)

#        externallinks = []

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
