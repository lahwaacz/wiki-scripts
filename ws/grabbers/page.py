#!/usr/bin/env python3

import datetime
import random

import ws.utils
from ws.parser_helpers.title import Title

def gen_inserts_from_page(api, page):
    title = Title(api, page["title"])

    # items for page table
    db_entry = {
        "page_id": page["pageid"],
        "page_namespace": page["ns"],
        # title is stored without the namespace prefix
        "page_title": title.pagename,
        "page_is_redirect": "redirect" in page,
        "page_is_new": "new" in page,
        "page_random": random.random(),
        "page_touched": page["touched"],
        "page_links_updated": None,
        "page_latest": page["lastrevid"],
        "page_len": page["length"],
        "page_content_model": page["contentmodel"],
        "page_lang": page["pagelanguage"],
    }
    yield "insert", db_entry

    # items for page_props table
    for propname, value in page.get("pageprops", {}).items():
        db_entry = {
            "pp_page": page["pageid"],
            "pp_propname": propname,
            "pp_value": value,
            # TODO: how should this be populated?
#            "pp_sortkey": 
        }
        yield "insert", db_entry

    # items for page_restrictions table
    for pr in page["protection"]:
        # drop entries caused by cascading protection
        if "source" not in pr:
            db_entry = {
                "pr_page": page["pageid"],
                "pr_type": pr["type"],
                "pr_level": pr["level"],
                "pr_cascade": "cascade" in pr,
                "pr_user": None,    # unused
                "pr_expiry": pr["expiry"],
            }
            yield "insert", db_entry


def gen_deletes_from_page(api, page):
    if "missing" in page:
        # deleted page - this will cause cascade deletion in
        # page_props and page_restrictions tables
        yield "delete-page", page["pageid"]
    else:
        # delete outdated props
        props = set(page.get("pageprops", {}))
        yield "delete-pp!", (page["pageid"], props)

        # delete outdated restrictions
        applied = set(pr["type"] for pr in page["protection"])
        yield "delete-pr!", (page["pageid"], applied)


def gen_insert(api):
    params = {
        "generator": "allpages",
        "gaplimit": "max",
        "prop": "info|pageprops",
        "inprop": "protection",
    }
    for ns in api.site.namespaces.keys():
        if ns < 0:
            continue
        params["gapnamespace"] = ns
        for page in api.generator(params):
            yield from gen_inserts_from_page(api, page)


def gen_update(api, rcpages):
    logger.info("Fetching properties of {} modified pages...".format(len(rcpages)))
    for chunk in ws.utils.iter_chunks(rcusers, api.max_ids_per_query):
        params = {
            "action": "query",
            "pageids": "|".join(chunk),
            "prop": "info|pageprops",
            "inprop": "protection",
        }
        for page in gen(api, params):
            yield from gen_inserts_from_page(api, page)
            yield from gen_deletes_from_page(api, page)


def gen_rcpages(api, since):
    since_f = ws.utils.format_date(since)
    rcpages = set()

    # Items in the recentchanges table are periodically purged according to
    # http://www.mediawiki.org/wiki/Manual:$wgRCMaxAge
    # By default the max age is 13 weeks: if a larger timespan is requested
    # here, it's very important to warn that the changes are not available
    if api.oldest_recent_change > since:
        raise ShortRecentChangesError()

    rc_params = {
        "action": "query",
        "list": "recentchanges",
        "rctype": "edit|new|log",
        "rcprop": "ids",
        "rclimit": "max",
        "rcdir": "newer",
        "rcstart": since_f,
    }
    for change in api.list(rc_params):
        # add pageid for edits, new pages and target pages of log events
        rcpages.add(change["pageid"])

        # TODO: examine logs (needs rcprop=loginfo)
        # move, protect, delete are handled by the above
        # these deserve special treatment
        #   merge       (revision - or maybe page too?)
        #   import      (everything?)
        #   patrol      (page)  (not in recentchanges! so we can't know when a page loses its 'new' flag)
        #   suppress    (everything?)
#        if change["type"] == "log":
#            if change["logtype"] == "merge":
#                ...

    return rcpages


def db_execute(db, gen):
    page_ins = db.page.insert(mysql_on_duplicate_key_update=[
                                    db.page.c.page_namespace,
                                    db.page.c.page_title,
                                    db.page.c.page_is_redirect,
                                    db.page.c.page_is_new,
                                    db.page.c.page_random,
                                    db.page.c.page_touched,
                                    db.page.c.page_links_updated,
                                    db.page.c.page_latest,
                                    db.page.c.page_len,
                                    db.page.c.page_content_model,
                                    db.page.c.page_lang,
                                ])
    pp_ins = db.page_props.insert(mysql_on_duplicate_key_update=[
                                    db.page_props.c.pp_value,
                                ])
    pr_ins = db.page_restrictions.insert(mysql_on_duplicate_key_update=[
                                    db.page_restrictions.c.pr_level,
                                    db.page_restrictions.c.pr_cascade,
                                    db.page_restrictions.c.pr_user,
                                    db.page_restrictions.c.pr_expiry,
                                ])

    for chunk in ws.utils.iter_chunks(gen, db.chunk_size):
        # separate according to action and target table
        page_ins_entries = []
        pp_ins_entries = []
        pr_ins_entries = []
        page_del_pageids = []
        pp_invdel_entries = []
        pr_invdel_entries = []

        for action, entry in chunk:
            if action == "insert":
                if "page_id" in entry:
                    page_ins_entries.append(entry)
                elif "pp_page" in entry:
                    pp_ins_entries.append(entry)
                elif "pr_page" in entry:
                    pr_ins_entries.append(entry)
                else:  # pragma: no cover
                    raise Exception
            elif action == "delete-page":
                page_del_pageids.append(entry)
            elif action == "delete-pp!":
                pp_invdel_entries.append(entry)
            elif action == "delete-pr!":
                pr_invdel_entries.append(entry)
            else:  # pragma: no cover
                raise Exception


        with db.engine.begin() as conn:
            if page_ins_entries:
                conn.execute(page_ins, page_ins_entries)
            if pp_ins_entries:
                conn.execute(pp_ins, pp_ins_entries)
            if pr_ins_entries:
                conn.execute(pr_ins, pr_ins_entries)

            if page_del_pageids:
                conn.execute(db.page.delete().where(page.c.page_id in page_del_pageids))

            for pageid, props in pp_invdel_entries:
                conn.execute(db.page_props.delete().where(
                                page_props.c.pr_page == pageid and \
                                page_props.c.pr_propname not in props))

            for pageid, applied_prs in pr_invdel_entries:
                conn.execute(db.page_restrictions.delete().where(
                                page_restrictions.c.pr_page == pageid and \
                                page_restrictions.c.pr_type not in applied_prs))


def insert(api, db):
    # delete everything and start over, otherwise the invalid rows would stay
    # in the tables
    with db.engine.begin() as conn:
        conn.execute(db.page.delete())
        conn.execute(db.page_props.delete())
        conn.execute(db.page_restrictions.delete())

    sync_timestamp = datetime.datetime.utcnow()

    gen = gen_insert(api)
    db_execute(db, gen)

    db.set_sync_timestamp(db.page, sync_timestamp)


def update(api, db):
    sync_timestamp = datetime.datetime.utcnow()
    since = db.get_sync_timestamp(db.page)
    if since is None:
        insert(api, db)
        return

    try:
        rcpages = set(gen_rcpages(api, since))
    except ShortRecentChangesError:
        logger.warning("The recent changes table on the wiki has been recently purged, starting from scratch.")
        insert(api, db)
        return

    if len(rcpages) > 0:
        gen = gen_update(api, rcusers)
        db_execute(db, gen)

        db.set_sync_timestamp(db.page, sync_timestamp)
