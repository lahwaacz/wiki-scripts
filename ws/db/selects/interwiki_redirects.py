#!/usr/bin/env python3

import sqlalchemy as sa

def get_interwiki_redirects(db):
    nss = db.namespace_starname
    page = db.page
    rd = db.redirect
    query = sa.select([nss.c.nss_name, page.c.page_title, rd.c.rd_interwiki, rd.c.rd_title, rd.c.rd_fragment]) \
            .select_from(
                    page.outerjoin(nss, page.c.page_namespace == nss.c.nss_id)
                        .join(rd, page.c.page_id == rd.c.rd_from)
                ) \
            .where(db.redirect.c.rd_interwiki != None)

    interwiki_redirects = {}

    conn = db.engine.connect()
    for row in conn.execute(query):
        source = db.Title("")
        source._set_namespace(row["nss_name"])
        source._set_pagename(row["page_title"])

        target = db.Title("")
        target._set_iwprefix(row["rd_interwiki"])
        target._set_pagename(row["rd_title"])
        target._set_sectionname(row["rd_fragment"] or "")

        interwiki_redirects[str(source)] = str(target)

    return interwiki_redirects
