#!/usr/bin/env python3

import random

import ws.utils

def gen(api):
    for ns in api.site.namespaces.keys():
        if ns < 0:
            continue
        for page in api.generator(
                    generator="allpages",
                    gaplimit="max",
                    gapnamespace=ns,
                    prop="info|pageprops",
                    inprop="protection",
                ):

            # init for page table
            db_entry = {
                "page_id": page["pageid"],
                "page_namespace": page["ns"],
                # TODO: strip namespace prefix
                "page_title": page["title"],
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

            # add items for page_props table
            for propname, value in page.get("pageprops", {}).items():
                db_entry.update({
                    "pp_page": page["pageid"],
                    "pp_propname": propname,
                    "pp_value": value,
                    # TODO: how should this be populated?
#                    "pp_sortkey": 
                })

            # add items for page_restrictions table
            for pr in page.get("protection", []):
                # drop entries caused by cascading protection
                if "source" not in pr:
                    db_entry.update({
                        "pr_page": page["pageid"],
                        "pr_type": pr["type"],
                        "pr_level": pr["level"],
                        "pr_cascade": "cascade" in pr,
                        "pr_user": None,    # unused
                        "pr_expiry": pr["expiry"],
                    })

            yield db_entry

def insert(api, db):
    page_ins = db.page.insert()
    pp_ins = db.page_props.insert()
    pr_ins = db.page_restrictions.insert()

    # delete everything and start over, otherwise the invalid rows would stay
    # in the table
    # (TODO: it may be possible to do this better way...)
    with db.engine.begin() as conn:
        conn.execute(db.page.delete())
        conn.execute(db.page_props.delete())
        conn.execute(db.page_restrictions.delete())

    for chunk in ws.utils.iter_chunks(gen(api), db.chunk_size):
        entries = list(chunk)

        with db.engine.begin() as conn:
            conn.execute(page_ins, entries)

            pp_entries = [e for e in entries if "pp_page" in e]
            if len(pp_entries) > 0:
                conn.execute(pp_ins, pp_entries)

            pr_entries = [e for e in entries if "pr_page" in e]
            if len(pr_entries) > 0:
                conn.execute(pr_ins, pr_entries)

def select(db):
    page_sel = db.page.select()
    pp_sel = db.page_props.select()
    pr_sel = db.page_restrictions.select()

    # TODO: reconstructing the API entries will be hard, after all the data were fetched with a generator
    raise NotImplementedError
