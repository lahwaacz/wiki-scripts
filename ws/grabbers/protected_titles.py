#!/usr/bin/env python3

import ws.utils

def gen(api):
    for pt in api.list(list="protectedtitles", ptlimit="max", ptprop="timestamp|userid|comment|expiry|level"):
        db_entry = {
            "pt_namespace": pt["ns"],
            "pt_title": pt["title"],
            "pt_user": int(pt["userid"]),
            "pt_reason": pt["comment"],
            "pt_timestamp": pt["timestamp"],
            "pt_expiry": pt["expiry"],
            "pt_create_perm": pt["level"],
        }
        yield db_entry

def insert(api, db):
    pt_ins = db.protected_titles.insert()

    conn = db.engine.connect()

    # delete everything and start over, otherwise the invalid rows would stay
    # in the table
    # (TODO: it may be possible to do this better way...)
    conn.execute(db.protected_titles.delete())

    for chunk in ws.utils.iter_chunks(gen(api), db.chunk_size):
        entries = list(chunk)
        conn.execute(pt_ins, entries)

def select(db):
    pt_sel = db.protected_titles.select()

    conn = db.engine.connect()
    result = conn.execute(pt_sel)

    for row in result:
        api_entry = {
            "ns": row.pt_namespace,
            "title": row.pt_title,
            "user": row.pt_user,
            "comment": row.pt_reason,
            "timestamp": row.pt_timestamp,
            "expiry": row.pt_expiry,
            "level": row.pt_create_perm,
        }
        yield api_entry
