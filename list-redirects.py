#! /usr/bin/env python3

import os.path

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

# To resolve the redirects, the list of pageids must be split into chunks to fit
# the limit for pageids= parameter. This can't be done on snippets returned by
# API.query_continue(), because the limit for pageids is *lower* than for the
# generator (for both normal and apihighlimits)
#
# See also https://wiki.archlinux.org/index.php/User:Lahwaacz/Notes#API:_resolving_redirects

# check if we have apihighlimits and adjust the limit
limit = 500 if api.has_high_limits() else 50

# resolve by chunks
redirects = []
for snippet in list_chunks(pageids, limit):
    result = api.call(action="query", redirects="", pageids="|".join(snippet))
    redirects.extend(result["redirects"])



# according to ArchWiki standards, the title must be sentence-case (if it is not an acronym)
# we will print the wrong capitalized redirects, i.e. when sentence-case title redirects to title-case

# first limit to redirects whose source and target title differ only in capitalization
redirects = [r for r in redirects if r["from"].lower() == r["to"].lower()]

# sort by source title
redirects.sort(key=lambda r: r["from"])

# we will count the number of uppercase letters
def count_uppercase(text):
    return sum(1 for c in text if c.isupper())

for r in redirects:
    if count_uppercase(r["from"]) < count_uppercase(r["to"]):
        print("* [[%s]] --> [[%s]]" % (r["from"], r["to"]))
