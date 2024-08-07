#! /usr/bin/env python3

import os.path

from ws.client import API
from ws.diff import diff_revisions

api_url = "https://wiki.archlinux.org/api.php"
index_url = "https://wiki.arclinux.org/index.php"
session = API.make_session()

api = API(api_url, index_url, session)


# show the diff for two revisions, colorized for 256-color terminal
oldrevid = 625761
newrevid = 625800

print(diff_revisions(api, oldrevid, newrevid))
