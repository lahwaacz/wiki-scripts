#!/usr/bin/env python3

import sqlalchemy as sa

def gen_namespace(api):
    for ns in api.site.namespaces.values():
        # don't store special namespaces in the database
        if ns["id"] < 0:
            continue

        db_entry = {
            "ns_id": ns["id"],
            "ns_case": ns["case"],
            "ns_content": "content" in ns,
            "ns_subpages": "subpages" in ns,
            "ns_nonincludable": "nonincludable" in ns,
            # TODO: is this even available from the API?
            "ns_defaultcontentmodel": None,
        }
        yield db_entry


def gen_namespace_name(api):
    for ns in api.site.namespaces.values():
        # don't store special namespaces in the database
        if ns["id"] < 0:
            continue

        # main namespace does not have a canonical name
        if "canonical" in ns:
            nsn_canonical = ns["*"] == ns["canonical"]
        else:
            nsn_canonical = False

        db_entry = {
            "nsn_id": ns["id"],
            "nsn_name": ns["*"],
            "nsn_starname": True,
            "nsn_canonical": nsn_canonical,
            "nsn_alias": False,
        }
        yield db_entry

        if nsn_canonical is False and "canonical" in ns:
            db_entry = {
                "nsn_id": ns["id"],
                "nsn_name": ns["canonical"],
                "nsn_starname": False,
                "nsn_canonical": True,
                "nsn_alias": False,
            }
            yield db_entry

    for alias in api.site.namespacealiases.values():
        db_entry = {
            "nsn_id": alias["id"],
            "nsn_name": alias["*"],
            "nsn_starname": False,
            "nsn_canonical": False,
            "nsn_alias": True,
        }
        yield db_entry


# TODO: delete namespaces that ceased to exist
def update(api, db):
    ns_ins = db.namespace.insert(mysql_on_duplicate_key_update=[
                                db.namespace.c.ns_case,
                                db.namespace.c.ns_content,
                                db.namespace.c.ns_subpages,
                                db.namespace.c.ns_nonincludable,
                                db.namespace.c.ns_defaultcontentmodel,
                            ])
    nsn_ins = db.namespace_name.insert(mysql_on_duplicate_key_update=[
                                db.namespace_name.c.nsn_id,
                                db.namespace_name.c.nsn_starname,
                                db.namespace_name.c.nsn_canonical,
                                db.namespace_name.c.nsn_alias,
                            ])

    ns_entries = list(gen_namespace(api))
    if ns_entries:
        with db.engine.begin() as conn:
            conn.execute(ns_ins, ns_entries)

    nsn_entries = list(gen_namespace_name(api))
    if nsn_entries:
        with db.engine.begin() as conn:
            conn.execute(nsn_ins, nsn_entries)


def select(db):
    ns_sel = db.namespace.select()
    nsn_sel = db.namespace_name.select()

    conn = db.engine.connect()
    result = conn.execute(ns_sel)

    namespaces = {}

    for row in result:
        ns = {
            "id": row.ns_id,
            "case": row.ns_case,
        }
        if row.ns_content:
            ns["content"] = ""
        if row.ns_subpages:
            ns["subpages"] = ""
        if row.ns_nonincludable:
            ns["nonincludable"] = ""
        namespaces[row.ns_id] = ns

    result = conn.execute(nsn_sel)
    for row in result:
        if row.nsn_starname:
            namespaces[row.nsn_id]["*"] = row.nsn_name
        if row.nsn_canonical:
            namespaces[row.nsn_id]["canonical"] = row.nsn_name

    return namespaces
