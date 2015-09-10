#! /usr/bin/env python3

import itertools

from ws.core import API
from ws.ArchWiki.lang import detect_language

def main(api):
    templates = [
        "Template:Article summary start",
        "Template:Article summary heading",
        "Template:Article summary link",
        "Template:Article summary text",
        "Template:Article summary wiki",
        "Template:Article summary end"
    ]
    pages_gen = (api.generator(generator="embeddedin", geilimit="max", geititle=title) for title in templates)
    pages = itertools.chain.from_iterable(pages_gen)
    titles = set(page["title"] for page in pages)

    # print only languages for which "Template:Related articles start (<lang>)" exists
    langs_whitelist = ["English", "Español", "Italiano", "Português", "Česky", "Ελληνικά", "Русский", "正體中文", "简体中文", "한국어"]

    for title in sorted(titles):
        # detect language, check whitelist
        _, lang = detect_language(title)
        if lang in langs_whitelist:
            print("* [[%s]]" % title)
#            print("** https://wiki.archlinux.org/index.php/%s" % title.replace(" ", "_"))

if __name__ == "__main__":
    import ws.config
    api = ws.config.object_from_argparser(API, description="List pages transcluding any of the deprecated Article summary templates")
    main(api)
