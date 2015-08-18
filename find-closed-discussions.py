#! /usr/bin/env python3

import re

from ws.core import API
import ws.cache

def main(api, db):
    namespaces = ["1", "5", "11", "13", "15"]
    talks = []
    closed_talk_re = re.compile("^[=]+[ ]*<s>", flags=re.MULTILINE)
    for ns in namespaces:
        pages = db[ns]
        for page in pages:
            title = page["title"]
            text = page["revisions"][0]["*"]
            if re.search(closed_talk_re, text):
                talks.append(page)

    # commit data to disk in case there were lazy updates
    # TODO: check if there were actually some updates...
    db.dump()

    for page in talks:
        print("* [[{}]]".format(page["title"]))

if __name__ == "__main__":
    import ws.config
    import ws.logging

    argparser = ws.config.getArgParser(description="Find closed discussions")
    API.set_argparser(argparser)
    args = argparser.parse_args()

    # set up logging
    ws.logging.init(args)

    api = API.from_argparser(args)
    # FIXME: except for this part, object_from_argparser could be used
    db = ws.cache.LatestRevisionsText(api, args.cache_dir, autocommit=False)

    main(api, db)
