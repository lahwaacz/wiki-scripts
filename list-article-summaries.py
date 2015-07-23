#! /usr/bin/env python3

import os.path

from ws.core import API
from ws.utils import flatten_gen
from ws.ArchWiki.lang import detect_language

api_url = "https://wiki.archlinux.org/api.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")

api = API(api_url, cookie_file=cookie_path, ssl_verify=True)

# print only easy-to-fix pages
as_in = api.generator(generator="embeddedin", geilimit="max", geititle="Template:Article summary wiki")
#as_out = flatten_gen( (api.generator(generator="embeddedin", geilimit="max", geititle=title) for title in ["Template:Article summary heading", "Template:Article summary link", "Template:Article summary text"]) )
as_out = flatten_gen( (api.generator(generator="embeddedin", geilimit="max", geititle=title) for title in ["Template:Article summary link"]) )

titles_out = [p["title"] for p in as_out if p["ns"] == 0]

# print only languages for which "Template:Related articles start (<lang>)" exists
langs_whitelist = ["English", "Español", "Italiano", "Português", "Česky", "Ελληνικά", "Русский", "正體中文", "简体中文", "한국어"]

for page in sorted(as_in , key=lambda d: d["title"]):
    title = page["title"]
    if page["ns"] == 0 and title not in titles_out:
        # detect language, check whitelist
        if detect_language(title)[1] in langs_whitelist:
            print("* [[%s]]" % title)
#            print("** https://wiki.archlinux.org/index.php/%s" % title.replace(" ", "_"))
