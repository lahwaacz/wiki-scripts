#! /usr/bin/env python3

import os.path
from collections import namedtuple
import itertools

from ws.client import API
import ws.ArchWiki.lang as lang

api_url = "https://wiki.archlinux.org/api.php"
index_url = "https://wiki.arclinux.org/index.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")
session = API.make_session(ssl_verify=True,
                           cookie_file=cookie_path)

api = API(api_url, index_url, session)

Page = namedtuple("Page", ["title", "langname", "pure"])

pages = []
for page in api.generator(generator="allpages", gaplimit="max", gapfilterredir="nonredirects"):
    pure, langname = lang.detect_language(page["title"])
    pages.append(Page(page["title"], langname, pure))

pages.sort(key=lambda page: (page.langname, page.pure))

groups = itertools.groupby(pages, key=lambda page: page.langname)
for langname, pages in groups:
    print("== {} ==\n".format(langname))
    for page in pages:
        print("* [[:{}|{}]]".format(page.title, page.pure))
    print()
