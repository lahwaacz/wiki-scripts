#! /usr/bin/env python3

import os.path
import re

from MediaWiki import API, diff_highlighted
from utils import *

api_url = "https://wiki.archlinux.org/api.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.bot.cookie")

api = API(api_url, cookie_file=cookie_path, ssl_verify=True)


# Loop through a list of pages, extract list of wiki links, filter out non-redirect
# links and update the links over redirects __if and only if__ the target page and
# redirect page's titles differ only in capitalization.
#
# See also https://wiki.archlinux.org/index.php?title=Help_talk:Style&oldid=328391#Links_to_redirects

# ask url of the page to find backlinks for
url = input("page url: ")
title = url.replace("https://wiki.archlinux.org/index.php/", "")
title = title.split("#")[0]
print("page title: '%s'" % title)

# pages to operate on
pages = api.generator(generator="backlinks", gbltitle=title, gbllimit="max", gblnamespace="0|4|12", gblredirect="")

for page in sorted(pages, key=lambda x: x["title"]):
    print("Processing page '%s'" % page["title"])
    # get wiki links on the page
    links = api.generator(generator="links", pageids=page["pageid"], gpllimit="max", prop="info")
    # limit to links over redirects
    links = [link for link in links if link.get("redirect") is not None]

    # resolve redirects
    redirects = api.resolve_redirects([str(link["pageid"]) for link in links])

    # limit to redirects whose source and target title differ only in capitalization
    redirects = [r for r in redirects if r["from"].lower() == r["to"].lower()]

    print("Found %d links over redirect (unique)" % len(redirects))
    if len(redirects) > 0:
        result = api.call(action="query", prop="revisions", rvprop="content", pageids=page["pageid"])
        _p = list(result["pages"].values())[0]
        text = _p["revisions"][0]["*"]
        text_orig = text    # save orig for the diff

        # for each redirect apply the regex substitution according to
        # https://wiki.archlinux.org/index.php?title=User:Lahwaacz.bot&diff=323281&oldid=322615
        for r in redirects:
            old = r["from"]
            new = r["to"]
            regex = re.compile(r"(\[\[|\{\{Related2?\|)[ _]*([%s%s])%s[ _]*(#|\||\]\]|\}\})" % (old[0].upper(), old[0].lower(), "[ _]".join(old[1:].split())))
            
            # check if the first word of the new title is an acronym
            if all(c.upper() == c for c in new.split()[0]):
                text = re.sub(regex, r"\1%s\3" % new, text)
            else:
                # preserve case of the first letter for non-acronym titles
                text = re.sub(regex, r"\1\2%s\3" % new[1:], text)

        # interactive
        diff = diff_highlighted(text_orig, text)
        options = [
            ("y", "make this edit"),
            ("n", "do not make this edit"),
            ("q", "quit; do not make this edit or any of the following"),
#            ("e", "manually edit this edit"),
            ("?", "print help"),
        ]
        short_options = [o[0] for o in options]
        ans = ""
        while True:
            print(diff)
            ans = input("Make this edit? [%s]? " % ",".join(short_options))
            if ans == "?" or ans not in short_options:
                for o in options:
                    print("%s - %s" % o)
            else:
                break

        if ans == "y":
            result = api.edit(page["pageid"], text, "update link(s) (avoid redirect if the titles differ only in capitalization) (testing https://github.com/lahwaacz/wiki-scripts/blob/master/fix-links-avoid-redirect.py)", minor="", bot="")
        elif ans == "q":
            break
