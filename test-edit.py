#! /usr/bin/env python3

import os.path

from MediaWiki import API, RevisionDiffer

api_url = "https://wiki.archlinux.org/api.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")

api = API(api_url, cookie_file=cookie_path, ssl_verify=True)

# get content of ArchWiki:Sandbox
result = api.call(action="query", prop="revisions", rvprop="content|timestamp", titles="ArchWiki:Sandbox")
page = list(result["pages"].values())[0]
text = page["revisions"][0]["*"]
timestamp = page["revisions"][0]["timestamp"]

result = api.edit(page["pageid"], text.replace("test", "text"), timestamp, "test")

# show the diff (depends on python-pygments)
diff = RevisionDiffer(api)
print(diff.diff(result["oldrevid"], result["newrevid"]))
