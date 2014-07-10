#! /usr/bin/env python3

import os.path
from datetime import datetime

from MediaWiki import API
from utils import *

api_url = "https://wiki.archlinux.org/api.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")

api = API(api_url, cookie_file=cookie_path, ssl_verify=True)

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
now = datetime.utcnow()
for user in users:
    delta = now - parse_date(user["registration"])
    user["avgeditsperday"] = user["editcount"] / delta.days if delta.days != 0 else user["editcount"]

#users.sort(key=lambda u: u["editcount"], reverse=True)
#users.sort(key=lambda u: u["recenteditcount"], reverse=True)
users.sort(key=lambda u: u["avgeditsperday"], reverse=True)

for user in users:
    print(user)
