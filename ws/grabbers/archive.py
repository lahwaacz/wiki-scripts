#!/usr/bin/env python3

from sqlalchemy import bindparam

import ws.utils

def gen(api):
    _props = "ids|timestamp|flags|user|userid|comment|size|sha1|contentmodel"
    for page in api.list(list="alldeletedrevisions", adrlimit="max", adrprop=_props):
        rev = page["revisions"][0]
        db_entry = {
            "ar_namespace": page["ns"],
            "ar_title": page["title"],
            "ar_comment": rev["comment"],
            "ar_user": rev["userid"],
            "ar_user_text": rev["user"],
            "ar_timestamp": rev["timestamp"],
            "ar_minor_edit": "minor" in rev,
            "ar_rev_id": rev["revid"],
            # ar_text_id will be set while populating the text table
            # TODO: ar_deleted
            "ar_len": rev["size"],
            "ar_page_id": page["pageid"],
            # TODO: ar_parent_id should be populated from revision.rev_parent_id
            "ar_sha1": rev["sha1"],
            "ar_content_model": rev["contentmodel"],
            # bound parameter used in update queries
            "b_rev_id": rev["revid"],
        }
        yield db_entry

def insert(api, db):
    ar_ins = db.archive.insert()

    conn = db.engine.connect()
    for chunk in ws.utils.iter_chunks(gen(api), db.chunk_size):
        entries = list(chunk)
        conn.execute(ar_ins, entries)

# TODO: not sure if pre-deletion is indeed useless
def update(api, db):
    ar_upd = db.archive.update().where(db.archive.c.ar_rev_id == bindparam("b_rev_id"))

    conn = db.engine.connect()
    for chunk in ws.utils.iter_chunks(gen(api), db.chunk_size):
        entries = list(chunk)
        conn.execute(ar_upd, entries)

def select(db):
    ar_sel = db.archive.select()
    # TODO: reconstructing the API entries will be hard, after all the data were fetched with a generator
    raise NotImplementedError
