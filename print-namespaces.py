#! /usr/bin/env python3

import os.path

from MediaWiki import API

api_url = "https://wiki.archlinux.org/api.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")

api = API(api_url, cookie_file=cookie_path, ssl_verify=True)


meta = api.call(action="query", meta="siteinfo", siprop="namespaces")
namespaces = meta["namespaces"].values()
for ns in sorted(namespaces, key=lambda x: x["id"]):
    if ns["*"] == "":
        ns["*"] = "Main"
    print("  %2d -- %s" % (ns["id"], ns["*"]))
