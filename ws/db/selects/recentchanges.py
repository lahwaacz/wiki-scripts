#!/usr/bin/env python3

import sqlalchemy as sa

import ws.db.mw_constants as mwconst


def set_defaults(params):
    params.setdefault("dir", "older")
    params.setdefault("prop", {"title", "timestamp", "ids"})
    params.setdefault("type", {"edit", "new", "log"})


def sanitize_params(params):
    assert set(params) <= {"start", "end", "dir", "namespace", "user", "excludeuser", "tag", "prop", "show", "type", "toponly", "limit", "continue"}

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

    # MW incompatibility: "parsedcomment" prop is not supported
    assert params["prop"] <= {"user", "userid", "comment", "flags", "timestamp", "title", "ids", "sizes", "patrolled", "loginfo", "sha1", "redirect", "tags"}

    # boolean flags
    # TODO: MediaWiki API has also "redirect" flag
    if "show" in params:
        flags = {"minor", "bot", "anon", "patrolled"}
        passed = set()
        for flag in params["show"]:
            assert flag in flags or "!" + flag in flags
            bare = flag.lstrip("!")
            assert bare not in passed
            passed.add(bare)

    assert params["type"] <= {"edit", "new", "log", "external"}


def list(db, params=None, **kwargs):
    """
    .. note::
        Parameters ``toponly=``, ``tag=``, ``prop=tags``, ``prop=sha1``,
        ``prop=redirect``, ``show=redirect`` require joins with other tables,
        so that information will not be present during mirroring.

        Also ``prop=title`` requires join with the ``namespace_starname`` table
        but that must be synchronized first anyway.
    """
    if params is None:
        params = kwargs
    elif not isinstance(params, dict):
        raise ValueError("params must be dict or None")
    elif kwargs and params:
        raise ValueError("specifying 'params' and 'kwargs' at the same time is not supported")

    set_defaults(params)
    sanitize_params(params)

    if {"limit", "continue"} & set(params):
        raise NotImplementedError

    rc = db.recentchanges
    s = sa.select([rc.c.rc_type, rc.c.rc_deleted])

    prop = params["prop"]
    if "user" in prop:
        s.append_column(rc.c.rc_user_text)
    if "userid" in prop:
        s.append_column(rc.c.rc_user)
    if "comment" in prop:
        s.append_column(rc.c.rc_comment)
    if "flags" in prop:
        s.append_column(rc.c.rc_minor)
        s.append_column(rc.c.rc_bot)
        s.append_column(rc.c.rc_new)
    if "timestamp" in prop:
        s.append_column(rc.c.rc_timestamp)
    if "title" in prop:
        s.append_column(rc.c.rc_namespace)
        s.append_column(rc.c.rc_title)
    if "ids" in prop:
        s.append_column(rc.c.rc_id)
        s.append_column(rc.c.rc_cur_id)
        s.append_column(rc.c.rc_this_oldid)
        s.append_column(rc.c.rc_last_oldid)
    if "sizes" in prop:
        s.append_column(rc.c.rc_old_len)
        s.append_column(rc.c.rc_new_len)
    if "patrolled" in prop:
        s.append_column(rc.c.rc_patrolled)
    if "loginfo" in prop:
        s.append_column(rc.c.rc_logid)
        s.append_column(rc.c.rc_log_type)
        s.append_column(rc.c.rc_log_action)
        s.append_column(rc.c.rc_params)

    # joins
    tail = rc
    if "title" in prop:
        nss = db.namespace_starname
        tail = tail.outerjoin(nss, rc.c.rc_namespace == nss.c.nss_id)
        s.append_column(nss.c.nss_name)
    if "sha1" in prop:
        rev = db.revision
        tail = tail.outerjoin(rev, rc.c.rc_this_oldid == rev.c.rev_id)
        s.append_column(rev.c.rev_sha1)
    if "toponly" in params or "redirect" in prop or {"redirect", "!redirect"} & params.get("show", set()):
        page = db.page
        tail = tail.outerjoin(page, (rc.c.rc_namespace == page.c.page_namespace) &
                                    (rc.c.rc_title == page.c.page_title))
        s.append_column(page.c.page_is_redirect)
    if "tags" in prop:
        tag = db.tag
        tgrc = db.tagged_recentchange
        # aggregate all tag names corresponding to the same revision into an array
        # (basically 'SELECT tgrc_rc_id, array_agg(tag_name) FROM tag JOIN tagged_recentchange GROUP BY tgrc_rc_id')
        # TODO: make a materialized view for this
        tag_names = sa.select([tgrc.c.tgrc_rc_id,
                               sa.func.array_agg(tag.c.tag_name).label("tag_names")]) \
                        .select_from(tag.join(tgrc, tag.c.tag_id == tgrc.c.tgrc_tag_id)) \
                        .group_by(tgrc.c.tgrc_rc_id) \
                        .cte("tag_names")
        tail = tail.outerjoin(tag_names, rc.c.rc_id == tag_names.c.tgrc_rc_id)
        if "tags" in prop:
            s.append_column(tag_names.c.tag_names)
    if "tag" in params:
        tag = db.tag
        tgrc = db.tagged_recentchange
        tail = tail.join(tgrc, rc.c.rc_id == tgrc.c.tgrc_rc_id)
        s = s.where(tgrc.c.tgrc_tag_id == sa.select([tag.c.tag_id]).where(tag.c.tag_name == params["tag"]))
    s = s.select_from(tail)

    # restrictions
    if "toponly" in params:
        s = s.where(rc.c.rc_this_oldid == page.c.page_latest)
    if params["dir"] == "older":
        newest = params.get("start")
        oldest = params.get("end")
    else:
        newest = params.get("end")
        oldest = params.get("start")
    if newest:
        s = s.where(rc.c.rc_timestamp < newest)
    if oldest:
        s = s.where(rc.c.rc_timestamp > oldest)
    if "namespace" in params:
        # FIXME: namespace can be a '|'-delimited list
        s = s.where(rc.c.rc_namespace == params["namespace"])
    if params.get("user"):
        s = s.where(rc.c.rc_user_text == params.get("user"))
    if params.get("excludeuser"):
        s = s.where(rc.c.rc_user_text != params.get("excludeuser"))
    s = s.where(rc.c.rc_type.in_(params["type"]))

    if "show" in params:
        show = params["show"]
        if "minor" in show:
            s = s.where(rc.c.rc_minor == True)
        elif "!minor" in show:
            s = s.where(rc.c.rc_minor == False)
        if "bot" in show:
            s = s.where(rc.c.rc_bot == True)
        elif "!bot" in show:
            s = s.where(rc.c.rc_bot == False)
        if "patrolled" in show:
            s = s.where(rc.c.rc_patrolled == True)
        elif "!patrolled" in show:
            s = s.where(rc.c.rc_patrolled == False)
        if "anon" in show:
            s = s.where(rc.c.rc_user == None)
        elif "!anon" in show:
            s = s.where(rc.c.rc_user != None)
        if "redirect" in show:
            s = s.where(page.c.page_is_redirect == True)
        elif "!redirect":
            # Don't throw log entries out the window here
            s = s.where( (page.c.page_is_redirect == False) |
                         (page.c.page_is_redirect == None) )

    # order by
    if params["dir"] == "older":
        s = s.order_by(rc.c.rc_timestamp.desc(), rc.c.rc_id.desc())
    else:
        s = s.order_by(rc.c.rc_timestamp.asc(), rc.c.rc_id.asc())

    result = db.engine.execute(s)
    for row in result:
        yield db_to_api(row)
    result.close()


def db_to_api(row):
    flags = {
        "rc_id": "rcid",
        "rc_timestamp": "timestamp",
        "rc_user": "userid",
        "rc_user_text": "user",
        "rc_namespace": "ns",
        "rc_comment": "comment",
        "rc_cur_id": "pageid",
        "rc_this_oldid": "revid",
        "rc_last_oldid": "old_revid",
        "rc_type": "type",
        "rc_old_len": "oldlen",
        "rc_new_len": "newlen",
        "rc_logid": "logid",
        "rc_log_type": "logtype",
        "rc_log_action": "logaction",
        "rc_params": "logparams",
        "rev_sha1": "sha1",
    }
    bool_flags = {
        "rc_minor": "minor",
        "rc_bot": "bot",
        "rc_new": "new",
        "rc_patrolled": "patrolled",
        "page_is_redirect": "redirect",
    }
    # subset of flags for which 0 should be used instead of None
    zeroable_flags = {"rc_user", "rc_cur_id", "rc_this_oldid", "rc_last_oldid"}

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
    if "nss_name" in row:
        if row["nss_name"]:
            api_entry["title"] = "{}:{}".format(row["nss_name"], row["rc_title"])
        else:
            api_entry["title"] = row["rc_title"]
    if "rc_user" in row and row["rc_user"] is None:
        api_entry["anon"] = ""
    # parse rc_deleted
    if row["rc_deleted"] & mwconst.DELETED_TEXT and row["rc_type"] != "log":
        api_entry["sha1hidden"] = ""
    if row["rc_deleted"] & mwconst.DELETED_ACTION and row["rc_type"] == "log":
        api_entry["actionhidden"] = ""
    if row["rc_deleted"] & mwconst.DELETED_COMMENT:
        api_entry["commenthidden"] = ""
    if row["rc_deleted"] & mwconst.DELETED_USER:
        api_entry["userhidden"] = ""
    if row["rc_deleted"] & mwconst.DELETED_RESTRICTED:
        api_entry["suppressed"] = ""
    # set tags to [] instead of None
    if "tag_names" in row:
        api_entry["tags"] = row["tag_names"] or []
        api_entry["tags"].sort()

    return api_entry


# TODO: this is needed only until list() supports limit parameter - then the caller can do the same as ws.client.api.API.oldest_rc_timestamp
def oldest_rc_timestamp(db):
    """
    Get timestamp of the oldest change stored in the recentchanges table.
    """
    result = db.engine.execute(sa.select( [sa.func.min(db.recentchanges.c.rc_timestamp)] ))
    return result.fetchone()[0]

def newest_rc_timestamp(db):
    """
    Get timestamp of the newest change stored in the recentchanges table.
    """
    result = db.engine.execute(sa.select( [sa.func.max(db.recentchanges.c.rc_timestamp)] ))
    return result.fetchone()[0]
