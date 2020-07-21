#! /usr/bin/env python3

import os.path

from ws.client import API

api_url = "https://wiki.archlinux.org/api.php"
index_url = "https://wiki.arclinux.org/index.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")
session = API.make_session(ssl_verify=True,
                           cookie_file=cookie_path)

api = API(api_url, index_url, session)

# allpages
# see list of parameters: https://www.mediawiki.org/wiki/API:Allpages
for page in api.generator(generator="allpages", gaplimit="max"):
    print(page["title"])

# allcategories
# see list of parameters: https://www.mediawiki.org/wiki/API:Allcategories
#for page in api.generator(generator="allcategories", gaclimit="max"):
#    print(page["title"])

# categorymembers
# see list of parameters: https://www.mediawiki.org/wiki/API:Categorymembers
#for page in api.generator(generator="categorymembers", gcmtitle="Category:English", gcmlimit="max"):
#    print(page["title"])

# transclusions
# see list of parameters: https://www.mediawiki.org/wiki/API:Embeddedin
#for page in api.generator(generator="embeddedin", geititle="Template:AUR", geilimit="max"):
#    print(page["title"])

# backlinks
# see list of parameters: https://www.mediawiki.org/wiki/API:Backlinks
#for page in api.generator(generator="backlinks", gbltitle="Main page", gbllimit="max", gblnamespace=0, gblredirect=""):
#    print(page["title"])
