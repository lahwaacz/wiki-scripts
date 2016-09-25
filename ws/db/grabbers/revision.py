#!/usr/bin/env python3

from pprint import pprint

import itertools
import sqlalchemy
from sqlalchemy import bindparam
from sqlalchemy.sql import func

import ws.utils

# this should be equal to the API's limit for the revids= parameter
#chunk_size_small = 500
# ...but must be less in order to not trip the PHP size limit
chunk_size_small = 100

# TODO: got many truncated results, should wait for list=allrevisions
def gen(api, first, last, with_content=False, text_id_gen=None):
    _props = "ids|timestamp|flags|user|userid|comment|size|sha1|contentmodel"
    if with_content is True:
        _props += "|content"
    for chunk in ws.utils.list_chunks(range(first, last+1), chunk_size_small):
        revids = "|".join(str(x) for x in chunk)
        for result in api.query_continue(action="query", revids=revids, prop="info|revisions|deletedrevisions", drvlimit="max", rvprop=_props, drvprop=_props):
            for _, page in result.get("pages", {}).items():
                revisions = itertools.chain(page.get("revisions", []), page.get("deletedrevisions", []))
                for rev in revisions:
                    db_entry = {
                        "rev_id": rev["revid"],
                        "rev_page": page.get("pageid"),
                        "rev_comment": rev["comment"],
                        "rev_user": rev["userid"],
                        "rev_user_text": rev["user"],
                        "rev_timestamp": rev["timestamp"],
                        "rev_minor_edit": "minor" in rev,
                        # TODO: rev_deleted
                        "rev_len": rev["size"],
                        # TODO: read on page history merging
                        "rev_parent_id": rev.get("parentid"),
                        "rev_sha1": rev["sha1"],
                        "rev_content_model": rev["contentmodel"],
                        # bound parameter used in update queries
                        "b_rev_id": rev["revid"],
                    }
                    if with_content is True:
                        text_id = next(text_id_gen)
                        db_entry.update({
                            "rev_text_id": text_id,
                            "old_id": text_id,
                            "old_text": rev["*"],
                            # TODO: possibility for compression
                            "old_flags": "utf-8",
                        })
                    yield db_entry

# TODO: text.old_id is auto-increment, but revision.rev_text_id has to be set accordingly. SQL should be able to do it automatically.
def _get_text_id(conn):
    result = conn.execute(sqlalchemy.select( [func.max(db.text.c.old_id)] ))
    value = result.fetchone()[0]
    if value is None:
        value = 0
    while True:
        value += 1
        yield value

def _get_last_revid_db(conn):
    """
    Get ID of the last revision stored in the cache database.
    """
    result = conn.execute(sqlalchemy.select( [func.max(db.revision.c.rev_id)] ))
    value = result.fetchone()[0]
    if value is None:
        return 0
    return value

def insert(api, db):
    revision_ins = db.revision.insert()
    text_ins = db.text.insert()

    conn = db.engine.connect()

    # get revision IDs
    firstrevid = 1
    midrevid = _get_last_revid_db(conn)
    lastrevid = api.last_revision_id

    text_id_gen = _get_text_id(conn)

    # update existing revisions
    # TODO: optimize, necessary only to update rev_page_id after history merging
    for chunk in ws.utils.iter_chunks(gen(api, firstrevid, midrevid), db.chunk_size):
        entries = list(chunk)
        conn.execute(revision_upd, entries)

    # insert new revisions
    for chunk in ws.utils.iter_chunks(gen(api, midrevid + 1, lastrevid, with_content=True, text_id_gen=text_id_gen), db.chunk_size):
        entries = list(chunk)
        conn.execute(revision_ins, entries)
        conn.execute(text_ins, entries)

def update(api, db):
    revision_upd = db.revision.update().where(db.revision.c.rev_id == bindparam("b_rev_id"))
    raise NotImplementedError

def select(db):
    # TODO: reconstructing the API entries will be hard, after all the data were fetched with a generator
#    raise NotImplementedError

    conn = db.engine.connect()
    s = sqlalchemy.select([db.revision, db.text.c.old_text]).where(
            db.revision.c.rev_text_id == db.text.c.old_id
        )
    for row in conn.execute(s):
        api_revision_entry = {
            "revid": row.rev_id,
            "comment": row.rev_comment,
            "userid": row.rev_user,
            "user": row.rev_user_text,
            "timestamp": row.rev_timestamp,
            # TODO: rev_deleted
            "size": row.rev_len,
            "parentid": row.rev_parent_id,
            "sha1": row.rev_sha1,
            "contentmodel": row.rev_content_model,
            "*": row.old_text,
        }
        if row.rev_minor_edit:
            api_revision_entry["minor"] = ""

        pprint(api_revision_entry)
