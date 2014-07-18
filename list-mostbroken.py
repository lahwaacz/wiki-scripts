#! /usr/bin/env python3

import os.path

from MediaWiki import API

api_url = "https://wiki.archlinux.org/api.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")

api = API(api_url, cookie_file=cookie_path, ssl_verify=True)

# return set of page titles transcluding 'title'
def get_transclusions(api, title):
    return set([page["title"] for page in api.list(list="embeddedin", eilimit="max", eititle=title, einamespace=0)])

# various "broken" pages
# see https://wiki.archlinux.org/index.php/ArchWiki:Requests#General_requests
accuracy = get_transclusions(api, "Template:Accuracy")
outofdate = get_transclusions(api, "Template:Out of date")
deletion = get_transclusions(api, "Template:Deletion")
expansion = get_transclusions(api, "Template:Expansion")
poorwriting = get_transclusions(api, "Template:Poor writing")
merge = get_transclusions(api, "Template:Merge")
moveto = get_transclusions(api, "Template:Moveto")
stub = get_transclusions(api, "Template:Stub")

all_ = accuracy | outofdate | deletion | expansion | poorwriting | merge | moveto | stub

# print titles based on some condition
# see Python set operations: https://docs.python.org/3.4/library/stdtypes.html#set

#for title in accuracy & outofdate:
#for title in deletion:
#for title in stub - deletion:
for title in accuracy - outofdate - expansion:
#for title in all_:
    print("* [[%s]]" % title)
