#! /usr/bin/env python3

import sys
import os.path

from pprint import pprint

from ws.core import API
from ws.interactive import require_login

api_url = "https://wiki.archlinux.org/api.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")

api = API(api_url, cookie_file=cookie_path, ssl_verify=True)
require_login(api)

# check for necessary rights
if "deletedhistory" not in api.user_rights():
    print("The current user does not have the 'deletedhistory' right, which is necessary to use this script. Sorry.")
    sys.exit(1)

pages = api.list(list="alldeletedrevisions", adrlimit="max")

pages_counts = {}
users_counts = {}

for page in pages:
    title = page["title"]
    pages_counts.setdefault(title, 0)
    for r in page.get("revisions", []):
        # print revision
        pprint(r)
        # increment counters
        pages_counts[title] += 1
        user = r["user"]
        users_counts.setdefault(user, 0)
        users_counts[user] += 1

# total count of deleted revisions
total_count = sum(count for _, count in pages_counts.items())
# count of pages with non-zero number of deleted revisions
pages_count = len([1 for _, count in pages_counts.items() if count > 0])
# count of users whose at least one revision has been deleted
users_count = len(users_counts.keys())

print("{} deleted revisions on {} pages by {} users".format(total_count, pages_count, users_count))

# print top 20 users with most deleted revisions
for user, count in sorted(users_counts.items(), key=lambda t: t[1], reverse=True)[:20]:
    print(user, count)
