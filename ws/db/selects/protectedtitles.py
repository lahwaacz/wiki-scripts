#!/usr/bin/env python3

import datetime

import sqlalchemy as sa

import ws.db.mw_constants as mwconst


def set_defaults(params):
    params.setdefault("dir", "older")
    params.setdefault("prop", {"timestamp", "level"})


def sanitize_params(params):
    assert set(params) <= {"start", "end", "dir", "namespace", "level", "prop", "limit", "continue"}

    # sanitize limits
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

    if "namespace" in params:
        assert isinstance(params["namespace"], set)
    if "level" in params:
        assert params["level"] <= {"autoconfirmed", "sysop"}

    # MW incompatibility: "parsedcomment" prop is not supported
    assert params["prop"] <= {"timestamp", "user", "userid", "comment", "expiry", "level"}


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

    if {"limit", "continue"} & set(params):
        raise NotImplementedError

    pt = db.protected_titles
    log = db.logging

    # join with logging to get the timestamp, user ID, user name and comment
    # inner select to get the corresponding log_id for the rows from protected_titles
    pt_inner = sa.select([*pt.c._all_columns, sa.func.max(log.c.log_id).label("pt_log_id")]) \
               .select_from(pt.outerjoin(log, sa.and_(pt.c.pt_namespace == log.c.log_namespace,
                                              pt.c.pt_title == log.c.log_title,
                                              log.c.log_type == "protect",
                                              log.c.log_action == "protect"))) \
               .group_by(*pt.c._all_columns) \
               .cte("pt_inner")
    # join pt_inner with logging again
    tail = pt_inner.outerjoin(log, pt_inner.c.pt_log_id == log.c.log_id)

    # join to get the namespace prefix
    nss = db.namespace_starname
    tail = tail.outerjoin(nss, pt_inner.c.pt_namespace == nss.c.nss_id)

    # select columns from pt_inner instead of protected_titles
    pt = pt_inner
    s = sa.select([pt.c.pt_namespace, pt.c.pt_title, nss.c.nss_name]) \
        .select_from(tail)

    prop = params["prop"]
    if "timestamp" in prop:
        s.append_column(log.c.log_timestamp)
    if "user" in prop:
        s.append_column(log.c.log_user_text)
    if "user" in prop or "userid" in prop:
        s.append_column(log.c.log_user)
    if "comment" in prop:
        s.append_column(log.c.log_comment)
    if "expiry" in prop:
        s.append_column(pt.c.pt_expiry)
    if "level" in prop:
        s.append_column(pt.c.pt_level)

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
    if "namespace" in params:
        s = s.where(log.c.log_namespace.in_(params["namespace"]))
    if "level" in params:
        s = s.where(pt.c.pt_level.in_(params["level"]))

    # order by
    if params["dir"] == "older":
        s = s.order_by(log.c.log_timestamp.desc(), pt.c.pt_namespace.desc(), pt.c.pt_title.desc())
    else:
        s = s.order_by(log.c.log_timestamp.asc(), pt.c.pt_namespace.asc(), pt.c.pt_title.asc())

    result = db.engine.execute(s)
    for row in result:
        yield db_to_api(row)
    result.close()


def db_to_api(row):
    flags = {
        "pt_namespace": "ns",
        "log_timestamp": "timestamp",
        "log_user_text": "user",
        "log_user": "userid",
        "log_comment": "comment",
        "pt_expiry": "expiry",
        "pt_level": "level",
    }
    bool_flags = {
    }
    # subset of flags for which 0 should be used instead of None
    zeroable_flags = {}

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
            api_entry["title"] = "{}:{}".format(row["nss_name"], row["pt_title"])
        else:
            api_entry["title"] = row["pt_title"]

    return api_entry
