#!/usr/bin/env python3

def get_namespaces(db):
    ns_sel = db.namespace.select()
    nss_sel = db.namespace_starname.select()
    nsc_sel = db.namespace_canonical.select()

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
        if row.ns_protection:
            ns["namespaceprotection"] = row.ns_protection
        namespaces[row.ns_id] = ns

    result = conn.execute(nss_sel)
    for row in result:
        namespaces[row.nss_id]["*"] = row.nss_name

    result = conn.execute(nsc_sel)
    for row in result:
        namespaces[row.nsc_id]["canonical"] = row.nsc_name

    return namespaces

def get_namespacenames(db):
    conn = db.engine.connect()
    result = conn.execute(db.namespace_name.select())

    namespacenames = {}

    for row in result:
        namespacenames[row.nsn_name] = row.nsn_id

    return namespacenames
