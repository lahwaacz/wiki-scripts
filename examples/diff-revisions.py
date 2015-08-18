#! /usr/bin/env python3

import os.path

from ws.core import API
from ws.diff import RevisionDiffer

api_url = "https://wiki.archlinux.org/api.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")

api = API(api_url, cookie_file=cookie_path, ssl_verify=True)


# show the diff for two revisions, colorized for 256-color terminal
oldrevid = 325013
newrevid = 325254

diff = RevisionDiffer(api)
print(diff.diff(oldrevid, newrevid))
