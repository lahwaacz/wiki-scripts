#!/usr/bin/env python3

import random

import ws.utils
from ws.parser_helpers.title import Title

def gen_from_page(api, page):
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
    for pr in page.get("protection", []):
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
            yield from gen_from_page(api, page)


def insert(api, db):
    page_ins = db.page.insert()
    pp_ins = db.page_props.insert()
    pr_ins = db.page_restrictions.insert()

    # delete everything and start over, otherwise the invalid rows would stay
    # in the tables
    with db.engine.begin() as conn:
        conn.execute(db.page.delete())
        conn.execute(db.page_props.delete())
        conn.execute(db.page_restrictions.delete())

    for chunk in ws.utils.iter_chunks(gen_insert(api), db.chunk_size):
        # separate according to target table
        page_entries = []
        pp_entries = []
        pr_entries = []
        for action, entry in chunk:
            assert action == "insert"
            if "page_id" in entry:
                page_entries.append(entry)
            elif "pp_page" in entry:
                pp_entries.append(entry)
            elif "pr_page" in entry:
                pr_entries.append(entry)
            else:  # pragma: no cover
                raise Exception

        with db.engine.begin() as conn:
            if page_entries:
                conn.execute(page_ins, page_entries)
            if pp_entries:
                conn.execute(pp_ins, pp_entries)
            if pr_entries:
                conn.execute(pr_ins, pr_entries)


def update(api, db):
    # TODO:
    # examine the logs for updates - log types to check out:
    #   move        (page)
    #   delete      (page)
    #   merge       (revision - or maybe page too?)
    #   protect     (page_restrictions table)
    #   import      (everything?)
    #   patrol      (page)
    #   suppress    (everything or just the logs?)
    # + maybe recentchanges for new pages (and added/removed props)
    raise NotImplementedError
