#!/usr/bin/env python3

from sqlalchemy import select
from sqlalchemy.sql import func

import ws.db.mw_constants as mwconst


def set_defaults(params):
    params.setdefault("dir", "older")
    params.setdefault("prop", {"ids", "title", "type", "user", "timestamp", "comment", "details"})


def sanitize_params(params):
    assert set(params) <= {"start", "end", "dir", "user", "title", "namespace", "prefix", "tag", "prop", "type", "action", "limit", "continue"}

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

    # MW incompatibility: "parsedcomment" prop is not supported
    assert params["prop"] <= {"user", "userid", "comment", "timestamp", "title", "ids", "type", "details", "tags"}
    # logically the set should not be empty - although: https://phabricator.wikimedia.org/T146556
    assert params["prop"]


def list(db, params=None, **kwargs):
    if params is None:
        params = kwargs
    elif not isinstance(params, dict):
        raise ValueError("params must be dict or None")
    elif kwargs and params:
        raise ValueError("specifying 'params' and 'kwargs' at the same time is not supported")

    set_defaults(params)
    sanitize_params(params)

    if {"prefix", "tag", "limit", "continue"} & set(params):
        raise NotImplementedError
    if "tags" in params["prop"]:
        raise NotImplementedError

    log = db.logging
    s = select([log.c.log_deleted])

    prop = params["prop"]
    if "user" in prop:
        s.append_column(log.c.log_user_text)
    if "userid" in prop:
        s.append_column(log.c.log_user)
    if "comment" in prop:
        s.append_column(log.c.log_comment)
    if "timestamp" in prop:
        s.append_column(log.c.log_timestamp)
    if "title" in prop:
        s.append_column(log.c.log_namespace)
        s.append_column(log.c.log_title)
    if "ids" in prop:
        s.append_column(log.c.log_id)
        s.append_column(log.c.log_page)
    if "type" in prop:
        s.append_column(log.c.log_type)
        s.append_column(log.c.log_action)
    if "details" in prop:
        s.append_column(log.c.log_params)

    # joins
    tail = log
    if "title" in prop:
        nss = db.namespace_starname
        tail = tail.outerjoin(nss, log.c.log_namespace == nss.c.nss_id)
        s.append_column(nss.c.nss_name)
        # TODO: MediaWiki says that page should be joined after user, test it
        page = db.page
        tail = tail.outerjoin(page, (log.c.log_namespace == page.c.page_namespace) &
                                    (log.c.log_title == page.c.page_title))
        s.append_column(page.c.page_id)
    if "user" in prop:
        user = db.user
        tail = tail.outerjoin(user, log.c.log_user == user.c.user_id)
        s.append_column(user.c.user_name)
    s = s.select_from(tail)

    # restrictions
    if params["dir"] == "older":
        newest = params.get("start")
        oldest = params.get("end")
    else:
        newest = params.get("end")
        oldest = params.get("start")
    if newest:
        s = s.where(log.c.log_timestamp < newest)
    if oldest:
        s = s.where(log.c.log_timestamp > oldest)
    if params.get("namespace"):
        s = s.where(log.c.log_namespace == params.get("namespace"))
    # TODO: something befor the caller and this function should split off the namespace prefix and pass namespace number
    if params.get("title"):
        s = s.where(log.c.log_title == params.get("title"))
    if params.get("user"):
        s = s.where(log.c.log_user_text == params.get("user"))
    # TODO
#    if params.get("prefix"):
    if params.get("type"):
        s = s.where(log.c.log_type == params.get("type"))
    # TODO: something should split action ("protect/modify" is "log_type/log_action")
    if params.get("action"):
        s = s.where(log.c.log_action == params.get("action"))

    # order by
    if params["dir"] == "older":
        s = s.order_by(log.c.log_timestamp.desc(), log.c.log_id.desc())
    else:
        s = s.order_by(log.c.log_timestamp.asc(), log.c.log_id.asc())

    result = db.engine.execute(s)
    for row in result:
        yield db_to_api(row)
    result.close()


def db_to_api(row):
    flags = {
        "log_id": "logid",
        "log_type": "type",
        "log_action": "action",
        "log_timestamp": "timestamp",
        "log_user": "userid",
        "log_user_text": "user",
        "log_namespace": "ns",
        "log_page": "logpage",
        "log_comment": "comment",
        "log_params": "params",
        "page_id": "pageid",
    }
    bool_flags = {}
    # subset of flags for which 0 should be used instead of None
    zeroable_flags = {"log_user", "log_page", "page_id"}

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
            api_entry["title"] = "{}:{}".format(row["nss_name"], row["log_title"])
        else:
            api_entry["title"] = row["log_title"]
    # use user name from the user table if available
    if "user_name" in row and row["user_name"]:
        api_entry["user"] = row["user_name"]
    if "log_user" in row and row["log_user"] is None:
        api_entry["anon"] = ""
    # parse log_deleted
    if row["log_deleted"] & mwconst.DELETED_ACTION:
        api_entry["actionhidden"] = ""
    if row["log_deleted"] & mwconst.DELETED_COMMENT:
        api_entry["commenthidden"] = ""
    if row["log_deleted"] & mwconst.DELETED_USER:
        api_entry["userhidden"] = ""
    if row["log_deleted"] & mwconst.DELETED_RESTRICTED:
        api_entry["suppressed"] = ""

    return api_entry
