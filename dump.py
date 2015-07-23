#! /usr/bin/env python3

import os.path
import sys

from ws.core import API
from ws.dump import DumpGenerator

api_url = "https://wiki.archlinux.org/api.php"
index_url = "https://wiki.archlinux.org/index.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")

api = API(api_url, cookie_file=cookie_path, ssl_verify=True)
dg = DumpGenerator(api, index_url, cookie_file=cookie_path, ssl_verify=True)

# TODO: take parameters from command line
r = dg.dump("stub/dump-test.xml", "2014-07-01T00:00:00Z")
sys.exit(not r)

