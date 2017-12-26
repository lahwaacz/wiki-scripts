#! /usr/bin/env python3

from ws.client import API

def main(api):
    # get titles of all pages in 'Main', 'ArchWiki' and 'Help' namespaces
    allpages = []
    for ns in ["0", "4", "12"]:
        _pages = api.generator(generator="allpages", gaplimit="max", gapnamespace=ns)
        allpages.extend([page["title"] for page in _pages])

    # get titles of all redirect pages in 'Talk', 'ArchWiki talk' and 'Help talk' namespaces
    talks = []
    for ns in ["1", "5", "13"]:
        pages = api.generator(generator="allpages", gaplimit="max", gapnamespace=ns)
        talks.extend([page["title"] for page in pages])

    # print talk pages of deleted pages
    for title in sorted(talks):
        _title = api.Title(title)
        if _title.articlepagename not in allpages:
            print("* [[%s]]" % title)

if __name__ == "__main__":
    import ws.config
    api = ws.config.object_from_argparser(API, description="List talk pages of deleted articles")
    main(api)
