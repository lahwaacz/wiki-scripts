#!/usr/bin/env python3

from sqlalchemy import select

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
    # TODO: MediaWiki API has also "redirect", "tags", "sha1" which require joins
    assert params["prop"] <= {"user", "userid", "comment", "flags", "timestamp", "title", "ids", "sizes", "patrolled", "loginfo"}

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
    if params is None:
        params = kwargs
    elif not isinstance(params, dict):
        raise ValueError("params must be dict or None")
    elif kwargs and params:
        raise ValueError("specifying 'params' and 'kwargs' at the same time is not supported")

    set_defaults(params)
    sanitize_params(params)

    if {"tag", "toponly", "limit", "continue"} & set(params):
        raise NotImplementedError

    rc = db.recentchanges
    s = select([rc.c.rc_type])

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
    if "title" in prop:
        nss = db.namespace_starname
        s = s.select_from(rc.outerjoin(nss, rc.c.rc_namespace == nss.c.nss_id))
        s.append_column(nss.c.nss_name)

    # restrictions
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
    if params.get("namespace"):
        s = s.where(rc.c.rc_namespace == params.get("namespace"))
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
            s = s.where(rc.c.rc_patrolled != None)

    # order by
    if params["dir"] == "older":
        s = s.order_by(rc.c.rc_timestamp.desc(), rc.c.rc_id.desc())
    else:
        s = s.order_by(rc.c.rc_timestamp.asc(), rc.c.rc_id.desc())

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
        # TODO
#        "rc_deleted":
        "rc_logid": "logid",
        "rc_log_type": "logtype",
        "rc_log_action": "logaction",
        "rc_params": "logparams",
    }
    bool_flags = {
        "rc_minor": "minor",
        "rc_bot": "bot",
        "rc_new": "new",
        "rc_patrolled": "patrolled",
    }

    api_entry = {}
    for key, value in row.items():
        if key in flags:
            # don't add None (log info for edits etc.)
            if value is not None:
                api_key = flags[key]
                api_entry[api_key] = value
        elif key in bool_flags:
            if value:
                api_key = bool_flags[key]
                api_entry[api_key] = ""

    # this should be the only special value (for now)
    if "nss_name" in row:
        if row["nss_name"]:
            api_entry["title"] = "{}:{}".format(row["nss_name"], row["rc_title"])
        else:
            api_entry["title"] = row["rc_title"]

    return api_entry
