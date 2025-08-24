#! /usr/bin/env python3

import logging
from functools import lru_cache

import mwparserfromhell
import requests.packages.urllib3 as urllib3
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

# TODO: generalize or make the language tags configurable
from ws.ArchWiki.lang import get_language_tags

from ..parser_helpers.template_expansion import expand_templates
from ..parser_helpers.title import TitleError
from ..parser_helpers.wikicode import get_anchors, is_redirect, parented_ifilter
from .selects.namespaces import get_namespaces

logger = logging.getLogger(__name__)

def get_normalized_extlinks(wikicode):
    # Pass 1: re-parse all external links, because "http://example.com/{{Dead link}}" was initially
    # parsed as one big URL, but the template transcludes tags which should terminate the URL.
#    for el in wikicode.filter_external_links(recursive=True):
#        wikicode.replace(el, str(el))
    # performance optimization, see https://github.com/earwig/mwparserfromhell/issues/195
    for parent, el in parented_ifilter(wikicode, forcetype=mwparserfromhell.nodes.external_link.ExternalLink, recursive=True):
        parent.replace(el, str(el), recursive=False)

    extlinks = wikicode.filter_external_links(recursive=True)

    # Pass 2: normalize the URLs
    for el in extlinks:
        # strip whitespace like "\t"
        el.url = str(el.url).strip()

    # Pass 3: skip invalid URLs
    filtered_extlinks = []
    for el in extlinks:
        try:
            # try to parse the URL - fails e.g. if port is not a number
            # reference: https://urllib3.readthedocs.io/en/latest/reference/urllib3.util.html#urllib3.util.parse_url
            url = urllib3.util.url.parse_url(str(el.url))
            # skip URLs with empty host, e.g. "http://" or "http://git@" or "http:///var/run"
            # (partial workaround for https://github.com/earwig/mwparserfromhell/issues/196 )
            # GOTCHA: mailto:user@host is scheme + path only; auth, host and port are recognized only after //
            if url.scheme != "mailto" and not url.host:
                continue
            filtered_extlinks.append(el)
        except urllib3.exceptions.LocationParseError:
            pass

    return filtered_extlinks

class ParserCache:
    def __init__(self, db):
        self.db = db
        self.invalidated_pageids = set()

        wspc_sync = self.db.ws_parser_cache_sync
        wspc_sync_ins = insert(wspc_sync)

        self.sql_inserts = {
            "templatelinks": self.db.templatelinks.insert(),
            "pagelinks": self.db.pagelinks.insert(),
            "imagelinks": self.db.imagelinks.insert(),
            "categorylinks": self.db.categorylinks.insert(),
            "langlinks": self.db.langlinks.insert(),
            "iwlinks": self.db.iwlinks.insert(),
            "externallinks": self.db.externallinks.insert(),
            "redirect": self.db.redirect.insert(),
            "section": self.db.section.insert(),
            "ws_parser_cache_sync":
                wspc_sync_ins.on_conflict_do_update(
                    constraint=wspc_sync.primary_key,
                    set_={"wspc_rev_id": wspc_sync_ins.excluded.wspc_rev_id}
                )
        }

    def _execute(self, conn, query, *, explain=False):
        if explain is True:
            from ws.db.database import explain
            with self.db.engine.connect() as conn:
                result = conn.execute(explain(query))
                print(query)
                for row in result:
                    print(row[0])

        return conn.execute(query)

    def _check_invalidation(self, conn):
        tl = self.db.templatelinks
        page = self.db.page
        wspc = self.db.ws_parser_cache_sync

        # pages with older revisions
        # (note that we don't join the templatelinks table here because we want
        # to invalidate also pages which don't have any template links)
        query = sa.select(page.c.page_id) \
                .select_from(
                    page.outerjoin(wspc, page.c.page_id == wspc.c.wspc_page_id)
                ).where(
                    ( wspc.c.wspc_rev_id == None ) |
                    ( wspc.c.wspc_rev_id != page.c.page_latest )
                )
        for row in self._execute(conn, query):
            self.invalidated_pageids.add(row.page_id)

        # pages transcluding older pages
        src_page = page.alias()
        target_page = page.alias()
        query = sa.select(src_page.c.page_id) \
                .select_from(
                    src_page.join(tl, tl.c.tl_from == src_page.c.page_id)
                    .join(target_page, ( tl.c.tl_namespace == target_page.c.page_namespace ) &
                                       ( tl.c.tl_title == target_page.c.page_title )
                    )
                    .outerjoin(wspc, target_page.c.page_id == wspc.c.wspc_page_id)
                ).where(
                    ( wspc.c.wspc_rev_id == None ) |
                    ( wspc.c.wspc_rev_id != target_page.c.page_latest )
                )
        for row in self._execute(conn, query):
            self.invalidated_pageids.add(row.page_id)

    def _invalidate(self, conn):
        conn.execute(self.db.pagelinks.delete().where(self.db.pagelinks.c.pl_from.in_(self.invalidated_pageids)))
        conn.execute(self.db.templatelinks.delete().where(self.db.templatelinks.c.tl_from.in_(self.invalidated_pageids)))
        conn.execute(self.db.imagelinks.delete().where(self.db.imagelinks.c.il_from.in_(self.invalidated_pageids)))
        conn.execute(self.db.categorylinks.delete().where(self.db.categorylinks.c.cl_from.in_(self.invalidated_pageids)))
        conn.execute(self.db.langlinks.delete().where(self.db.langlinks.c.ll_from.in_(self.invalidated_pageids)))
        conn.execute(self.db.iwlinks.delete().where(self.db.iwlinks.c.iwl_from.in_(self.invalidated_pageids)))
        conn.execute(self.db.externallinks.delete().where(self.db.externallinks.c.el_from.in_(self.invalidated_pageids)))
        conn.execute(self.db.redirect.delete().where(self.db.redirect.c.rd_from.in_(self.invalidated_pageids)))
        conn.execute(self.db.section.delete().where(self.db.section.c.sec_page.in_(self.invalidated_pageids)))

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
            conn.execute(self.sql_inserts["templatelinks"], db_entries)

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
        db_entries = list({ (v["pl_from"], v["pl_namespace"], v["pl_title"] ): v for v in db_entries}.values())

        if db_entries:
            conn.execute(self.sql_inserts["pagelinks"], db_entries)

    def _insert_imagelinks(self, conn, pageid, imagelinks):
        db_entries = []
        for title in imagelinks:
            entry = {
                "il_from": pageid,
                "il_to": title.pagename,
            }
            db_entries.append(entry)

        # drop duplicates
        db_entries = list({ (v["il_from"], v["il_to"] ): v for v in db_entries}.values())

        if db_entries:
            conn.execute(self.sql_inserts["imagelinks"], db_entries)

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
        db_entries = list({ (v["cl_from"], v["cl_to"] ): v for v in db_entries}.values())

        if db_entries:
            conn.execute(self.sql_inserts["categorylinks"], db_entries)

    def _insert_langlinks(self, conn, pageid, langlinks):
        db_entries = []
        for title in langlinks:
            if title.namespace:
                ll_title = "{}:{}".format(title.namespace, title.pagename)
            else:
                ll_title = title.pagename
            # language links to specific section are a thing...
            if title.sectionname:
                ll_title += "#" + title.sectionname
            entry = {
                "ll_from": pageid,
                "ll_lang": title.iwprefix,
                "ll_title": ll_title,
            }
            db_entries.append(entry)

        # drop duplicates
        db_entries = list({ (v["ll_from"], v["ll_lang"] ): v for v in db_entries}.values())

        if db_entries:
            conn.execute(self.sql_inserts["langlinks"], db_entries)

    def _insert_iwlinks(self, conn, pageid, iwlinks):
        db_entries = []
        for title in iwlinks:
            entry = {
                "iwl_from": pageid,
                "iwl_prefix": title.iwprefix,
                "iwl_title": "{}:{}".format(title.namespace, title.pagename) if title.namespace else title.pagename
            }
            db_entries.append(entry)

        # drop duplicates
        db_entries = list({ (v["iwl_from"], v["iwl_prefix"], v["iwl_title"] ): v for v in db_entries}.values())

        if db_entries:
            conn.execute(self.sql_inserts["iwlinks"], db_entries)

    def _insert_externallinks(self, conn, pageid, externallinks):
        db_entries = []
        for ext in externallinks:
            url = str(ext.url)
            entry = {
                "el_from": pageid,
                "el_to": url,
            }
            db_entries.append(entry)

        # drop duplicates
        db_entries = list({ (v["el_from"], v["el_to"] ): v for v in db_entries}.values())

        if db_entries:
            conn.execute(self.sql_inserts["externallinks"], db_entries)

    def _insert_redirect(self, conn, pageid, target):
        db_entry = {
            "rd_from": pageid,
            "rd_namespace": target.namespacenumber if not target.iwprefix else None,
        }

        if target.iwprefix:
            db_entry["rd_interwiki"] = target.iwprefix
            if target.namespace:
                db_entry["rd_title"] = "{}:{}".format(target.namespace, target.pagename)
            else:
                db_entry["rd_title"] = target.pagename
        else:
            db_entry["rd_title"] = target.pagename

        if target.sectionname:
            db_entry["rd_fragment"] = target.sectionname

        conn.execute(self.sql_inserts["redirect"], db_entry)

    def _insert_section(self, conn, pageid, levels, headings):
        if headings:
            anchors = get_anchors(headings)

            db_entries = []
            for i, level, title, anchor in zip(range(len(headings)), levels, headings, anchors):
                db_entry = {
                    "sec_page": pageid,
                    "sec_number": i + 1,
                    "sec_level": level,
                    "sec_title": title,
                    "sec_anchor": anchor,
                }
                db_entries.append(db_entry)

            conn.execute(self.sql_inserts["section"], db_entries)

    def _set_sync_revid(self, conn, pageid, revid):
        """
        Set the ``pageid``, ``revid`` pair in the ``ws_parser_cache_sync`` table.
        """
        entry = {
            "wspc_page_id": pageid,
            "wspc_rev_id": revid,
        }
        conn.execute(self.sql_inserts["ws_parser_cache_sync"], entry)

    # cacheable part of the content getter, using common cache across all SQL transactions
    @lru_cache(maxsize=128)
    def _cached_content_getter(self, title):
        pages_gen = self.db.query(titles=title, prop="latestrevisions", rvprop="content", rvslots="main")
        page = next(pages_gen)

        if "revisions" in page:
            if "*" in page["revisions"][0]["slots"]["main"]:
                return page["revisions"][0]["slots"]["main"]["*"]
            else:
                logger.error("ParserCache: no latest revision found for page [[{}]]".format(page["title"]))
                raise ValueError
        else:
            # no revision => page does not exist
            logger.warn("ParserCache: page not found: {{" + title + "}}")
            raise ValueError

    def _parse_page(self, conn, pageid, title, content):
        logger.info("ParserCache: parsing page [[{}]] ...".format(title))
        title = self.db.Title(title)

        # set of all pages transcluded on the current page
        # (will be filled by the content_getter function)
        transclusions = set()

        def content_getter(title):
            # skip pages in the Special: and Media: namespaces
            # (even MediaWiki does not track such transclusions in the templatelinks table)
            if title.namespacenumber < 0:
                raise ValueError
            # set and lru_cache need hashable types
            title = str(title)
            nonlocal transclusions
            transclusions.add(title)
            return self._cached_content_getter(title)

        wikicode = mwparserfromhell.parse(content)
        expand_templates(title, wikicode, content_getter)

        logger.debug("ParserCache: content getter cache statistics: {}".format(self._cached_content_getter.cache_info()))

        # templatelinks can be updated right away
        self._insert_templatelinks(conn, pageid, transclusions)

        # parse redirect using regex-based parser helper
        if is_redirect(str(wikicode)):
            page_is_redirect = True
            # the redirect target is just the first wikilink
            redirect_target = wikicode.filter_wikilinks()[0]
            self._insert_redirect(conn, pageid, self.db.Title(str(redirect_target.title)))
        else:
            page_is_redirect = False

        # replace HTML entities like "&#61" or "&Sigma;" with their unicode equivalents
#        for entity in wikicode.ifilter_html_entities(recursive=True):
#            wikicode.replace(entity, entity.normalize())
        # performance optimization, see https://github.com/earwig/mwparserfromhell/issues/195
        for parent, entity in parented_ifilter(wikicode, forcetype=mwparserfromhell.nodes.html_entity.HTMLEntity, recursive=True):
            parent.replace(entity, entity.normalize(), recursive=False)

        # normalize and extract external links
        # (should be done before wikilinks and other nodes, because URLs need to be re-parsed due to adjacent templates)
        extlinks = get_normalized_extlinks(wikicode)
        self._insert_externallinks(conn, pageid, extlinks)

        pagelinks = []
        imagelinks = []
        categorylinks = []
        langlinks = []
        iwlinks = []

        # classify all wikilinks
        for i, wl in enumerate(wikicode.ifilter_wikilinks(recursive=True)):
            try:
                base_target = self.db.Title(wl.title)
                target = base_target.make_absolute(title)
            except TitleError:
                logger.error("ParserCache: wikilink {} leads to an invalid title. Missing magic word implementation?".format(wl))
                continue

            if target.iwprefix:
                # language links cannot have a leading colon
                if target.leading_colon:
                    iwlinks.append(target)
                # the redirect link cannot be a language link
                elif page_is_redirect and i == 0:
                    iwlinks.append(target)
                # language links are special only in article namespaces, not in talk namespaces
                elif target.iwprefix in get_language_tags() and title.namespace == title.articlespace:
                    langlinks.append(target)
                else:
                    iwlinks.append(target)
                continue

            # redirects to special namespaces are not treated as special
            elif page_is_redirect is False or i > 0:
                if target.namespacenumber == -2:
                    # MediaWiki treats all links to the Media: namespace as imagelinks
                    imagelinks.append(target)
                    continue
                elif target.namespacenumber == 6 and not target.leading_colon:
                    imagelinks.append(target)
                    continue
                elif target.namespacenumber == 14 and not target.leading_colon:
                    # MW incompatibility: category links for automatic categories like
                    # "Pages with broken file links" are not supported
                    categorylinks.append( (target, str(wl.text) if wl.text else "") )
                    continue

            # MediaWiki tracks same-page links iff they have both page and section name.
            # For example, on page "Foo", [[Foo#Bar]] is tracked, but [[Foo]] and [[#Bar]]
            # are not.
            if target.namespace != title.namespace or target.pagename != title.pagename or (base_target.pagename and target.sectionname):
                # MediaWiki does not track links to the Special: namespace, Media: is treated like File:
                if target.namespacenumber == -2:
                    target.namespace = target.context.namespaces[6]["*"]
                if target.namespacenumber >= 0:
                    pagelinks.append(target)

        self._insert_pagelinks(conn, pageid, pagelinks)
        self._insert_iwlinks(conn, pageid, iwlinks)
        self._insert_categorylinks(conn, pageid, title, categorylinks)
        self._insert_langlinks(conn, pageid, langlinks)
        self._insert_imagelinks(conn, pageid, imagelinks)

        # extract section headings
        levels = []
        headings = []
        for heading in wikicode.ifilter_headings(recursive=True):
            levels.append(heading.level)
            headings.append(heading.title.strip())
        self._insert_section(conn, pageid, levels, headings)

    def update(self):
        self.invalidated_pageids = set()
        namespaces = get_namespaces(self.db)

        logger.info("ParserCache: Invalidating old entries...")
        with self.db.engine.begin() as conn:
            self._check_invalidation(conn)
            self._invalidate(conn)
        logger.debug("Invalidated pageids: {}".format(self.invalidated_pageids))

        if not self.invalidated_pageids:
            logger.info("ParserCache: All latest revisions have already been parsed.")
            return

        logger.info("ParserCache: Parsing new content...")

        def parse_namespace(ns):
            for page in self.db.query(generator="allpages", gapnamespace=ns, prop="latestrevisions", rvprop={"content", "ids"}, rvslots="main"):
                # one transaction per page
                with self.db.engine.begin() as conn:
                    if "*" in page["revisions"][0]["slots"]["main"]:
                        if page["pageid"] in self.invalidated_pageids:
                            self._parse_page(conn, page["pageid"], page["title"], page["revisions"][0]["slots"]["main"]["*"])
                            self._set_sync_revid(conn, page["pageid"], page["revisions"][0]["revid"])
                    else:
                        logger.error("ParserCache: no latest revision found for page [[{}]]".format(page["title"]))

        # parse templates before the main namespace so that we can interrupt afterwards
        parse_namespace(10)

        for ns in sorted(namespaces.keys()):
            if ns < 0 or ns == 10:
                continue
            parse_namespace(ns)

    def invalidate_all(self):
        with self.db.engine.begin() as conn:
            conn.execute(self.db.ws_parser_cache_sync.delete())

    def invalidate_pageids(self, pageids):
        with self.db.engine.begin() as conn:
            conn.execute(self.db.ws_parser_cache_sync.delete()
                    .where(
                        self.db.ws_parser_cache_sync.c.wspc_page_id.in_(pageids)
                    )
                )
