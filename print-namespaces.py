#! /usr/bin/env python3

import os.path

from ws.core import API
from ws.logging import setTerminalLogging

setTerminalLogging()

api_url = "https://wiki.archlinux.org/api.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")

api = API(api_url, cookie_file=cookie_path, ssl_verify=True)

for id_ in sorted(api.namespaces.keys()):
    ns = api.namespaces[id_]
    if ns == "":
        ns = "Main"
    print("  %2d -- %s" % (id_, ns))
