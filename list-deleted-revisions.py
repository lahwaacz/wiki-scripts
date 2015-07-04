#! /usr/bin/env python3

import sys
import os.path

from MediaWiki import API
from MediaWiki.interactive import require_login

api_url = "https://wiki.archlinux.org/api.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")

api = API(api_url, cookie_file=cookie_path, ssl_verify=True)
require_login(api)

# check for necessary rights
if "deletedhistory" not in api.user_rights():
    print("The current user does not have the 'deletedhistory' right, which is necessary to use this script. Sorry.")
    sys.exit(1)

for page in api.list(list="deletedrevs", drunique="", drlimit="max"):
    print(page["title"])
