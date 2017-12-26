#!/usr/bin/env python3

import sqlalchemy as sa

def get_interwikimap(db):
    conn = db.engine.connect()
    result = conn.execute(db.interwiki.select())

    interwikimap = {}

    for row in result:
        iw = {
            "prefix": row.iw_prefix,
            "url": row.iw_url,
        }
        if row.iw_local:
            iw["local"] = ""
        if row.iw_trans:
            iw["trans"] = ""
        if row.iw_api:
            iw["api"] = row.iw_api
        interwikimap[row.iw_prefix] = iw

    return interwikimap
