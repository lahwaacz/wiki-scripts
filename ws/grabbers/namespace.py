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
def update_namespace(api, db):
    ns_sel = sa.select([db.namespace.c.ns_id])
    ns_ins = db.namespace.insert()
    ns_upd = db.namespace.update() \
             .where(db.namespace.c.ns_id == sa.bindparam("b_ns_id"))

    # select only ns_id so we know what's in the db
    existing_namespaces = set()
    with db.engine.begin() as conn:
        for row in conn.execute(ns_sel):
            existing_namespaces.add(row.ns_id)

    # divide the API entries for insert or update
    ins_entries = []
    upd_entries = []
    for entry in gen_namespace(api):
        if entry["ns_id"] in existing_namespaces:
            # change ns_id to b_ns_id to make bindparam in the update statement work
            entry["b_ns_id"] = entry.pop("ns_id")
            upd_entries.append(entry)
        else:
            ins_entries.append(entry)

    with db.engine.begin() as conn:
        # insert new namespaces
        if ins_entries:
            conn.execute(ns_ins, ins_entries)

        # update existing namespaces
        if upd_entries:
            conn.execute(ns_upd, upd_entries)


def update_namespace_name(api, db):
    nsn_sel = sa.select([db.namespace_name.c.nsn_name])
    nsn_ins = db.namespace_name.insert()
    nsn_upd = db.namespace_name.update() \
              .where(db.namespace_name.c.nsn_name == sa.bindparam("b_nsn_name"))

    # select only nsn_name so we know what's in the db
    existing_names = set()
    with db.engine.begin() as conn:
        for row in conn.execute(nsn_sel):
            existing_names.add(row.nsn_name)

    # divide the API entries for insert or update
    ins_entries = []
    upd_entries = []
    for entry in gen_namespace_name(api):
        if entry["nsn_name"] in existing_names:
            # change ns_id to b_ns_id to make bindparam in the update statement work
            entry["b_nsn_name"] = entry.pop("nsn_name")
            upd_entries.append(entry)
        else:
            ins_entries.append(entry)

    with db.engine.begin() as conn:
        # insert new names
        if ins_entries:
            conn.execute(nsn_ins, ins_entries)

        # update existing names
        if upd_entries:
            conn.execute(nsn_upd, upd_entries)


def update(api, db):
    update_namespace(api, db)
    update_namespace_name(api, db)


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
