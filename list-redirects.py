#! /usr/bin/env python3

import os.path

from MediaWiki import API
from utils import *

api_url = "https://wiki.archlinux.org/api.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")

api = API(api_url, cookie_file=cookie_path, ssl_verify=True)


# first get list of pageids of redirect pages
pageids = []
for ns in ["0", "4", "12"]:
    pages = api.generator(generator="allpages", gaplimit="max", gapfilterredir="redirects", gapnamespace=ns)
    _pageids = [str(page["pageid"]) for page in pages]
    pageids.extend(_pageids)

# resolve redirects
redirects = api.resolve_redirects(pageids)


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
