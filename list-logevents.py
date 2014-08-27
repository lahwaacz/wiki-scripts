#! /usr/bin/env python3

import os.path
from pprint import pprint

from MediaWiki import API
from utils import *

api_url = "https://wiki.archlinux.org/api.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")

api = API(api_url, cookie_file=cookie_path, ssl_verify=True)


logs = api.list(list="logevents", letype="newusers", lelimit="max", ledir="newer")
logs = list(logs)

pprint(logs)

# these should be interesting
#pprint([i for i in logs if i["action"] != "create"])

print(len(logs))
