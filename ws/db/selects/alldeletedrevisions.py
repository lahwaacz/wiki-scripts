#!/usr/bin/env python3

import sqlalchemy as sa

import ws.db.mw_constants as mwconst


def set_defaults(params):
    params.setdefault("dir", "older")
    params.setdefault("prop", {"timestamp", "ids", "flags", "comment", "user"})


def sanitize_params(params):
    # MW incompatibility: parameters related to content parsing are not supported (they are deprecated anyway)
    assert set(params) <= {"start", "end", "dir", "namespace", "user", "excludeuser", "prop", "limit", "continue",
                           "section", "generatetitles",
                           "from", "to", "prefix", "tag"}  # these four are in addition to list=allrevisions

    # sanitize timestamp limits
    assert params["dir"] in {"newer", "older"}
    if params["dir"] == "older":
        newest = params.get("start")
        oldest = params.get("end")
    else:
        newest = params.get("end")
        oldest = params.get("start")
    # None is uncomparable
    if oldest and newest:
        assert oldest < newest

    assert "user" not in params or "excludeuser" not in params

    # MW incompatibility: "parsedcomment" and "parsetree" props are not supported
    assert params["prop"] <= {"user", "userid", "comment", "flags", "timestamp", "ids", "size", "sha1", "tags", "content", "contentmodel"}


def list(db, params=None, **kwargs):
    """
    .. note::
        Parameters ...TODO... require joins with other tables,
        so that information will not be present during mirroring.
    """
    if params is None:
        params = kwargs
    elif not isinstance(params, dict):
        raise ValueError("params must be dict or None")
    elif kwargs and params:
        raise ValueError("specifying 'params' and 'kwargs' at the same time is not supported")

    set_defaults(params)
    sanitize_params(params)

    if {"section", "generatetitles", "limit", "continue", "prefix"} & set(params):
        raise NotImplementedError

    ar = db.archive
    nss = db.namespace_starname
    page = db.page
    tail = ar.join(nss, ar.c.ar_namespace == nss.c.nss_id)
    s = sa.select([ar.c.ar_page_id, ar.c.ar_namespace, ar.c.ar_title, nss.c.nss_name, ar.c.ar_deleted])

    prop = params["prop"]
    if "user" in prop:
        s.append_column(ar.c.ar_user_text)
    if "userid" in prop:
        s.append_column(ar.c.ar_user)
    if "comment" in prop:
        s.append_column(ar.c.ar_comment)
    if "flags" in prop:
        s.append_column(ar.c.ar_minor_edit)
    if "timestamp" in prop:
        s.append_column(ar.c.ar_timestamp)
    if "ids" in prop:
        s.append_column(ar.c.ar_rev_id)
        s.append_column(ar.c.ar_parent_id)
    if "size" in prop:
        s.append_column(ar.c.ar_len)
    if "sha1" in prop:
        s.append_column(ar.c.ar_sha1)
    if "contentmodel" in prop:
        s.append_column(ar.c.ar_content_model)
        s.append_column(ar.c.ar_content_format)

    # joins
    if "content" in prop:
        tail = tail.outerjoin(db.text, ar.c.ar_text_id == db.text.c.old_id)
        s.append_column(db.text.c.old_text)
    if "tags" in prop:
        tag = db.tag
        tgar = db.tagged_archived_revision
        # aggregate all tag names corresponding to the same revision into an array
        # (basically 'SELECT tgar_rev_id, array_agg(tag_name) FROM tag JOIN tagged_recentchange GROUP BY tgar_rev_id')
        # TODO: make a materialized view for this
        tag_names = sa.select([tgar.c.tgar_rev_id,
                               sa.func.array_agg(tag.c.tag_name).label("tag_names")]) \
                        .select_from(tag.join(tgar, tag.c.tag_id == tgar.c.tgar_tag_id)) \
                        .group_by(tgar.c.tgar_rev_id) \
                        .cte("tag_names")
        tail = tail.outerjoin(tag_names, ar.c.ar_rev_id == tag_names.c.tgar_rev_id)
        s.append_column(tag_names.c.tag_names)
    if "tag" in params:
        tag = db.tag
        tgar = db.tagged_archived_revision
        tail = tail.join(tgar, ar.c.ar_rev_id == tgar.c.tgar_rev_id)
        s = s.where(tgar.c.tgar_tag_id == sa.select([tag.c.tag_id]).where(tag.c.tag_name == params["tag"]))
    s = s.select_from(tail)

    # restrictions
    if params["dir"] == "older":
        newest = params.get("start")
        oldest = params.get("end")
    else:
        newest = params.get("end")
        oldest = params.get("start")
    if newest:
        s = s.where(ar.c.ar_timestamp <= newest)
    if oldest:
        s = s.where(ar.c.ar_timestamp >= oldest)
    if "from" in params:
        s = s.where(ar.c.ar_title >= params["from"])
    if "end" in params:
        s = s.where(ar.c.ar_title <= params["to"])
    if "namespace" in params:
        # FIXME: namespace can be a '|'-delimited list
        s = s.where(page.c.page_namespace == params["namespace"])
    if params.get("user"):
        s = s.where(ar.c.ar_user_text == params.get("user"))
    if params.get("excludeuser"):
        s = s.where(ar.c.ar_user_text != params.get("excludeuser"))

    # order by
    if params["dir"] == "older":
        s = s.order_by(ar.c.ar_timestamp.desc(), ar.c.ar_rev_id.desc())
    else:
        s = s.order_by(ar.c.ar_timestamp.asc(), ar.c.ar_rev_id.asc())

    result = db.engine.execute(s)
    # TODO: group revisions per page like MediaWiki
    for row in result:
        yield db_to_api(row)
    result.close()


def db_to_api(row):
    flags = {
        "ar_rev_id": "revid",
        "ar_parent_id": "parentid",
        "ar_timestamp": "timestamp",
        "ar_user": "userid",
        "ar_user_text": "user",
        "ar_comment": "comment",
        "ar_sha1": "sha1",
        "ar_len": "size",
        "ar_content_model": "contentmodel",
        "ar_content_format": "contentformat",
        "old_text": "*",
        "ar_page_id": "pageid",
        "ar_namespace": "ns",
    }
    bool_flags = {
        "ar_minor_edit": "minor",
    }
    # subset of flags for which 0 should be used instead of None
    zeroable_flags = {"ar_user", "ar_parent_id"}

    api_entry = {}
    for key, value in row.items():
        if key in flags:
            api_key = flags[key]
            # normal keys are not added if the value is None
            if value is not None:
                api_entry[api_key] = value
            # some keys produce 0 instead of None
            elif key in zeroable_flags:
                api_entry[api_key] = 0
        elif key in bool_flags:
            if value:
                api_key = bool_flags[key]
                api_entry[api_key] = ""

    # add special values
    if row["nss_name"]:
        api_entry["title"] = "{}:{}".format(row["nss_name"], row["ar_title"])
    else:
        api_entry["title"] = row["ar_title"]
    if "rev_user" in row and row["rev_user"] is None:
        api_entry["anon"] = ""
    # parse ar_deleted
    if row["ar_deleted"] & mwconst.DELETED_TEXT:
        api_entry["sha1hidden"] = ""
    if row["ar_deleted"] & mwconst.DELETED_COMMENT:
        api_entry["commenthidden"] = ""
    if row["ar_deleted"] & mwconst.DELETED_USER:
        api_entry["userhidden"] = ""
    if row["ar_deleted"] & mwconst.DELETED_RESTRICTED:
        api_entry["suppressed"] = ""
    # set tags to [] instead of None
    if "tag_names" in row:
        api_entry["tags"] = row["tag_names"] or []
        api_entry["tags"].sort()

    return api_entry
