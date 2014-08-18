#! /usr/bin/env python3

import os.path
import re

from MediaWiki import API
from utils import *

api_url = "https://wiki.archlinux.org/api.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")

#api = API(api_url, cookie_file=cookie_path, ssl_verify=True)
api = API(api_url, ssl_verify=True)



# first get list of pageids of redirect pages
pageids = []
for ns in ["0", "4", "12"]:
    pages = api.generator(generator="allpages", gaplimit="max", gapfilterredir="redirects", gapnamespace=ns)
    _pageids = [str(page["pageid"]) for page in pages]
    pageids.extend(_pageids)

# resolve redirects
redirects = api.resolve_redirects(pageids)


# first limit to redirects with fragments
redirects = [r for r in redirects if r.get("tofragment") is not None]

# function to check if 'page' has 'section'
def has_section(page, section):
    result = api.call(action="query", prop="revisions", rvprop="content", titles=page)
    _p = list(result["pages"].values())[0]
    text = _p["revisions"][0]["*"]

    if re.search(r"^(\=+)( *)%s( *)\1$" % re.escape(section), text, re.MULTILINE):
#        print("page '%s' has section '%s'" % (page, section))
        return True
    else:
#        print("page '%s' does not have section '%s'" % (page, section))
        return False

# limit to redirects with broken fragment
redirects = [r for r in redirects if has_section(r["to"], r["tofragment"]) is False]

# sort by source title
redirects.sort(key=lambda r: r["from"])

for r in redirects:
    print("* [[%s]] --> [[%s#%s]]" % (r["from"], r["to"], r["tofragment"]))
