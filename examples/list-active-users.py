#! /usr/bin/env python3

import datetime

from ws.client import API

api_url = "https://wiki.archlinux.org/api.php"
index_url = "https://wiki.arclinux.org/index.php"
session = API.make_session()

api = API(api_url, index_url, session)

# get list of all users, who:
#   - are not bots
#   - made at least one edit
#   - have been active in the last 30 days
#   - are not blocked
# the list can be sorted by:
#   - editcount
#   - recenteditcount
#   - avgeditsperday (needs to be calculated)

users = list(api.list(list="allusers", aulimit="max", auprop="blockinfo|editcount|registration", auexcludegroup="bot", auwitheditsonly="", auactiveusers=""))

users = [user for user in users if user.get("blockid") is None]

# prepare sorting by avgeditsperday
now = datetime.datetime.utcnow()
for user in users:
    # exclude users with no registration date (some weird anomaly)  TODO: investigate
    if user["registration"] == "":
        user["avgeditsperday"] = 0
        continue

    delta = now - user["registration"]
    user["avgeditsperday"] = user["editcount"] / delta.days if delta.days != 0 else user["editcount"]

#users.sort(key=lambda u: u["editcount"], reverse=True)
#users.sort(key=lambda u: u["recenteditcount"], reverse=True)
users.sort(key=lambda u: u["avgeditsperday"], reverse=True)

for user in users:
    print(user)
