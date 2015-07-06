#! /usr/bin/env python3

import os
import re

from MediaWiki import API
import cache

api_url = "https://wiki.archlinux.org/api.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")

api = API(api_url, cookie_file=cookie_path, ssl_verify=True)
db = cache.LatestRevisionsText(api, autocommit=False)

namespaces = ["1", "5", "11", "13", "15"]
talks = []
closed_talk_re = re.compile("^[=]+[ ]*<s>", flags=re.MULTILINE)
for ns in namespaces:
    pages = db[ns]
    for page in pages:
        title = page["title"]
        text = page["revisions"][0]["*"]
        if re.search(closed_talk_re, text):
            talks.append(page)

# commit data to disk in case there were lazy updates
# TODO: check if there were actually some updates...
db.dump()

for page in talks:
    print("* [[{}]]".format(page["title"]))
