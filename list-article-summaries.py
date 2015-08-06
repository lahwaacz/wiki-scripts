#! /usr/bin/env python3

import os.path

from ws.core import API
from ws.utils import flatten_gen
from ws.ArchWiki.lang import detect_language
from ws.logging import setTerminalLogging

setTerminalLogging()

api_url = "https://wiki.archlinux.org/api.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")

api = API(api_url, cookie_file=cookie_path, ssl_verify=True)

templates = [
    "Template:Article summary start",
    "Template:Article summary heading",
    "Template:Article summary link",
    "Template:Article summary text",
    "Template:Article summary wiki",
    "Template:Article summary end"
]
pages = flatten_gen( (api.generator(generator="embeddedin", geilimit="max", geititle=title) for title in templates) )
titles = set(page["title"] for page in pages)

# print only languages for which "Template:Related articles start (<lang>)" exists
langs_whitelist = ["English", "Español", "Italiano", "Português", "Česky", "Ελληνικά", "Русский", "正體中文", "简体中文", "한국어"]

for title in sorted(titles):
    # detect language, check whitelist
    _, lang = detect_language(title)
    if lang in langs_whitelist:
        print("* [[%s]]" % title)
#        print("** https://wiki.archlinux.org/index.php/%s" % title.replace(" ", "_"))
