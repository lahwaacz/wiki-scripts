#!/usr/bin/env python3

from sqlalchemy import select

def list(db,
         start=None,
         end=None,
         dir="older",
         namespace=None,
         user=None,
         excludeuser=None,
# TODO
#         tag=None,
         prop=None,
         show=None,
         type=None):
# TODO
#         toponly=False,
#         limit="max",
#         continue_=None):

    # sanitize timestamp limits
    assert dir in {"newer", "older"}
    if dir == "older":
        newest = start
        oldest = end
    else:
        newest = end
        oldest = start
    # None is uncomparable
    if oldest and newest:
        assert oldest < newest

    assert user is None or excludeuser is None

    if prop is None:
        prop = {"title", "timestamp", "ids"}
    # MW incompatibility: "parsedcomment" prop is not supported
    # TODO: MediaWiki API has also "redirect", "tags", "sha1" which require joins
    assert prop <= {"user", "userid", "comment", "flags", "timestamp", "title", "ids", "sizes", "patrolled", "loginfo"}

    # boolean flags
    # TODO: MediaWiki API has also "redirect" flag
    if show is not None:
        flags = {"minor", "bot", "anon", "patrolled"}
        passed = set()
        for flag in show:
            assert flag in flags or "!" + flag in flags
            bare = flag.lstrip("!")
            assert bare not in passed
            passed.add(bare)

    if type is None:
        type = {"edit", "new", "log"}
    assert type <= {"edit", "new", "log", "external"}


    rc = db.recentchanges
    columns = {rc.c.rc_type}
    if "user" in prop:
        columns.add(rc.c.rc_user_text)
    if "userid" in prop:
        columns.add(rc.c.rc_user)
    if "comment" in prop:
        columns.add(rc.c.rc_comment)
    if "flags" in prop:
        columns.add(rc.c.rc_minor)
        columns.add(rc.c.rc_bot)
        columns.add(rc.c.rc_new)
    if "timestamp" in prop:
        columns.add(rc.c.rc_timestamp)
    if "title" in prop:
        columns.add(rc.c.rc_namespace)
        columns.add(rc.c.rc_title)
    if "ids" in prop:
        columns.add(rc.c.rc_id)
        columns.add(rc.c.rc_cur_id)
        columns.add(rc.c.rc_this_oldid)
        columns.add(rc.c.rc_last_oldid)
    if "sizes" in prop:
        columns.add(rc.c.rc_old_len)
        columns.add(rc.c.rc_new_len)
    if "patrolled" in prop:
        columns.add(rc.c.rc_patrolled)
    if "loginfo" in prop:
        columns.add(rc.c.rc_logid)
        columns.add(rc.c.rc_log_type)
        columns.add(rc.c.rc_log_action)
        columns.add(rc.c.rc_params)
    s = select(columns)

    # restrictions
    if newest:
        s = s.where(rc.c.rc_timestamp < newest)
    if oldest:
        s = s.where(rc.c.rc_timestamp > oldest)
    if namespace:
        s = s.where(rc.c.rc_namespace == namespace)
    if user:
        s = s.where(rc.c.rc_user_text == user)
    if excludeuser:
        s = s.where(rc.c.rc_user_text != user)
    s = s.where(rc.c.rc_type.in_(type))

    if show:
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
    if dir == "older":
        s = s.order_by(rc.c.rc_timestamp.desc(), rc.c.rc_id.desc())
    else:
        s = s.order_by(rc.c.rc_timestamp.asc(), rc.c.rc_id.desc())

    # TODO: transform the row into API format
    # TODO: combine namespace name and rc_title (write another function reading from ws_namespace table)
    result = db.engine.execute(s)
    for row in result:
        print(dict(row))
    result.close()
