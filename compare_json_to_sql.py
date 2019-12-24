#! /usr/bin/env python3

from pprint import pprint
from copy import deepcopy
from itertools import chain
import datetime
import json

from ws.client import API
from ws.interactive import require_login
from ws.db.database import Database
import ws.cache
from ws.utils.containers import dmerge

from grab import _check_lists

def compare_users(db_allusers, json_allusers):
    # note: simple check fails, json has more users
    #_check_lists(db_allusers, list(json_allusers))

    # note: some users from JSON don't have a userid
    json_valid_users = [user for user in json_allusers if "userid" in user]
    json_invalid_users = [user for user in json_allusers if "userid" not in user]
    print("Invalid users in the JSON database:")
    pprint(json_invalid_users)

    # normalize users from the JSON database for comparison
    for user in json_valid_users:
        # convert userid to int
        user["userid"] = int(user["userid"])
        if "blockid" in user:
            user["blockid"] = int(user["blockid"])
        if "blockedbyid" in user:
            user["blockedbyid"] = int(user["blockedbyid"])
        # delete recenteditcount - our select queries currently don't support that,
        # but it can be determined from the recentchanges table
        if "recenteditcount" in user:
            del user["recenteditcount"]
        # set empty registration to "" - sometimes it is None
        if not user["registration"]:
            user["registration"] = ""

    # sort user groups - neither we or MediaWiki do that
    for user in chain(db_allusers, json_valid_users):
        user["groups"].sort()

    # drop autoconfirmed - not reliably refreshed in the SQL database
    # TODO: try to fix that...
    for user in chain(db_allusers, json_valid_users):
        if "autoconfirmed" in user["groups"]:
            user["groups"].remove("autoconfirmed")

    # common users
    db_userids = set(user["userid"] for user in db_allusers)
    json_common_users = [user for user in json_valid_users if user["userid"] in db_userids]
    json_userids = set(user["userid"] for user in json_common_users)
    db_common_users = [user for user in db_allusers if user["userid"] in json_userids]

    # make sure that the lists are sorted the same way (sorting by name is affected by system and database locales)
    json_common_users.sort(key=lambda user: user["userid"])
    db_common_users.sort(key=lambda user: user["userid"])

    for db_user, json_user in zip(db_common_users, json_common_users):
        assert db_user["userid"] == json_user["userid"]
        # JSON cache has wrong editcount for a number of users - let's assume that the greatest editcount is correct
        if db_user["editcount"] > json_user["editcount"]:
            json_user["editcount"] = db_user["editcount"]
        # drop expired blocks
        if "blockexpiry" in json_user:
            expiry = json_user["blockexpiry"]
            if isinstance(expiry, str):
                expiry = datetime.datetime.strptime(expiry, '%Y%m%d%H%M%S')
            if expiry < datetime.datetime.utcnow():
                del json_user["blockedby"]
                del json_user["blockedbyid"]
                del json_user["blockedtimestamp"]
                del json_user["blockexpiry"]
                del json_user["blockid"]
                del json_user["blockreason"]

    _check_lists(db_common_users, json_common_users)

    # extra SQL users
    db_extra_users = [user for user in db_allusers if user["userid"] not in json_userids]
    if db_extra_users:
        print("Extra users from the SQL database:")
        pprint(db_extra_users)

    # extra JSON users
    json_extra_users = [user for user in json_valid_users if user["userid"] not in db_userids]
    if json_extra_users:
        print("Extra users from the JSON database:")
        pprint(json_extra_users)

def compare_revisions(db_allrevsprops, json_allrevsprops):
    # note: simple check fails, json has more revs
#    _check_lists(db_allrevsprops, json_allrevsprops)

    # re-sort by revid (lists of revisions and deletedrevisions were mereged)
    db_allrevsprops.sort(key=lambda rev: rev["revid"])
    json_allrevsprops.sort(key=lambda rev: rev["revid"])

    # drop SQL columns which are not stored in the JSON database
    for rev in db_allrevsprops:
        del rev["ns"]
        del rev["title"]
        del rev["pageid"]
        del rev["userid"]

    # these fields don't match, because JSON does not detect later updates
    for rev in chain(db_allrevsprops, json_allrevsprops):
        if "commenthidden" in rev:
            del rev["commenthidden"]
        if "sha1hidden" in rev:
            del rev["sha1hidden"]
        if "userhidden" in rev:
            del rev["userhidden"]
        # parentid was originally not available via API, then updated in the SQL database, but not in JSON
        if "parentid" in rev:
            del rev["parentid"]

        rev["timestamp"] = rev["timestamp"].isoformat()

    # common revs
    db_revids = set(rev["revid"] for rev in db_allrevsprops)
    json_common_revs = [rev for rev in json_allrevsprops if rev["revid"] in db_revids]
    json_revids = set(rev["revid"] for rev in json_common_revs)
    db_common_revs = [rev for rev in db_allrevsprops if rev["revid"] in json_revids]
    _check_lists(db_common_revs, json_common_revs)

    # extra SQL revs
    # db_extra_revs = [rev for rev in db_allrevsprops if rev["revid"] not in json_revids]
    # if db_extra_revs:
    #     print("Extra revisions from the SQL database:")
    #     pprint(db_extra_revs)

    # extra JSON revs
    json_extra_revs = [rev for rev in json_allrevsprops if rev["revid"] not in db_revids]
    if json_extra_revs:
        # print("Extra revisions from the JSON database:")
        print(json.dumps(json_extra_revs, indent=2, sort_keys=True))


if __name__ == "__main__":
    import ws.config
    import ws.logging

    argparser = ws.config.getArgParser()
    API.set_argparser(argparser)
    Database.set_argparser(argparser)

    args = argparser.parse_args()

    # set up logging
    ws.logging.init(args)

    api = API.from_argparser(args)
    require_login(api)
    db = Database.from_argparser(args)

    # sync the database
    db.sync_with_api(api)

    db_allusers = list(db.query(list="allusers", auprop={"groups", "blockinfo", "registration", "editcount"}))
    db_allrevsprops = list(db.query(list="allrevisions", arvlimit="max", arvdir="newer", arvprop={"ids", "flags", "timestamp", "user", "userid", "comment"}))
    db_alldeletedrevsprops = list(db.query(list="alldeletedrevisions", adrlimit="max", adrdir="newer", adrprop={"ids", "flags", "timestamp", "user", "userid", "comment"}))

    json_userprops = ws.cache.AllUsersProps(api, args.cache_dir, active_days=30, round_to_midnight=False, autocommit=False)
    json_allusers = deepcopy(list(json_userprops))
    json_allrevsprops = ws.cache.AllRevisionsProps(api, args.cache_dir, autocommit=False)
    json_allrevsprops_list = deepcopy(list(json_allrevsprops["revisions"]))
    json_alldeletedrevsprops_list = deepcopy(list(json_allrevsprops["deletedrevisions"]))

    # compare_users(db_allusers, json_allusers)
    compare_revisions(db_allrevsprops + db_alldeletedrevsprops, json_allrevsprops_list + json_alldeletedrevsprops_list)
