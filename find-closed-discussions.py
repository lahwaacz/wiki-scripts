#! /usr/bin/env python3

import re

from ws.client import API
from ws.db.database import Database

def main(api, db):
    db.sync_with_api(api)
    db.sync_latest_revisions_content(api)

    namespaces = ["1", "5", "11", "13", "15"]
    talks = []
    closed_talk_re = re.compile("^[=]+[ ]*<s>", flags=re.MULTILINE)
    for ns in namespaces:
        for page in db.query(generator="allpages", gapnamespace=ns, prop="latestrevisions", rvprop={"content"}):
            text = page["*"]
            if re.search(closed_talk_re, text):
                talks.append(page)

    for page in talks:
        print("* [[{}]]".format(page["title"]))

if __name__ == "__main__":
    import ws.config
    import ws.logging

    argparser = ws.config.getArgParser(description="Find closed discussions")
    API.set_argparser(argparser)
    Database.set_argparser(argparser)

    args = argparser.parse_args()

    # set up logging
    ws.logging.init(args)

    api = API.from_argparser(args)
    db = Database.from_argparser(args)

    main(api, db)
