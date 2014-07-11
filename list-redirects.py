#! /usr/bin/env python3

import os.path

from MediaWiki import API

api_url = "https://wiki.archlinux.org/api.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")

api = API(api_url, cookie_file=cookie_path, ssl_verify=True)
#api = API(api_url, ssl_verify=True)

# TODO: it is necessary to respect low/high limits !!!
#       otherwise we either exceed 50-pageids limit for "action=query&requests"
#       (yes, this is lower than for generator=allpages), or for high limits we
#       get '414: request-URI too large' error (gaplimit==5000 for apihighlimits)

redirects = []
_pageids = []
for ns in ["0", "4", "12"]:
    for snippet in api.query_continue(generator="allpages", gaplimit="500", gapfilterredir="redirects", gapnamespace=ns):
        snippet = sorted(snippet["pages"].values(), key=lambda d: d["title"])
        # first get list of pageids of redirect pages
        pageids = [str(page["pageid"]) for page in snippet]
        _pageids.extend(pageids)
#        print(len(pageids), len(list(set(pageids))))
        # then resolve them (get target titles)
        result = api.call(action="query", redirects="", pageids="|".join(pageids))
        redirects.extend(result["redirects"])
#        print("rl", len(redirects))

#print(redirects)
print(len(redirects))
print(len(_pageids))



# according to ArchWiki standards, the title must be sentence-case (if it is not an acronym)
# we will print the wrong capitalized redirects, i.e. when sentence-case title redirects to title-case

# first limit to redirects whose source and target title differ only in capitalization
redirects = [r for r in redirects if r["from"].lower() == r["to"].lower()]

# we will count the number of uppercase letters
def count_uppercase(text):
    return sum(1 for c in text if c.isupper())

for r in redirects:
    if count_uppercase(r["from"]) < count_uppercase(r["to"]):
        print("* [[%s]] --> [[%s]]" % (r["from"], r["to"]))
