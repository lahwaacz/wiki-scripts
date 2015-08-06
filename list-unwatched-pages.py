#! /usr/bin/env python3

import sys
import os.path

from ws.core import API
from ws.interactive import require_login
from ws.ArchWiki.lang import detect_language
from ws.logging import setTerminalLogging

setTerminalLogging()

api_url = "https://wiki.archlinux.org/api.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")

api = API(api_url, cookie_file=cookie_path, ssl_verify=True)
require_login(api)

# check for necessary rights
if "unwatchedpages" not in api.user_rights:
    print("The current user does not have the 'unwatchedpages' right, which is necessary to use this script. Sorry.")
    sys.exit(1)

# get list of unwatched pages
query_unwatched = {
    "action": "query",
    "list": "querypage",
    "qppage": "Unwatchedpages",
    "qplimit": "max",
    "continue": "",
}

# list flattening, limit to the Main namespace
unwatched = (page for snippet in api.query_continue(query_unwatched) for page in snippet["querypage"]["results"] if page["ns"] == 0)

# split into sections by language
by_language = {}
for page in unwatched:
    title = page["title"]
    lang = detect_language(title)[1]
    if lang not in by_language:
        by_language[lang] = []
    by_language[lang].append(title)

# print wikitext
for lang in sorted(by_language.keys()):
    print("== %s ==" % lang)
    print()
    for title in by_language[lang]:
        print("* %s" % title)
    print()
