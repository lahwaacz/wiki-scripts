#! /usr/bin/env python3

from ws.client import API
from ws.db.database import Database
from ws.utils.OrderedSet import OrderedSet

def main(api, db):
    db.sync_with_api(api)
    db.sync_revisions_content(api, mode="latest")
    db.update_parser_cache()

    namespaces = ["1", "5", "11", "13", "15"]
    talks = OrderedSet()
    for ns in namespaces:
        for page in db.query(generator="allpages", gapnamespace=ns, prop="sections", secprop={"title"}):
            for section in page.get("sections", []):
                if section["title"].startswith("<s>") and section["title"].endswith("</s>"):
                    talks.add(page["title"])

    for talk in talks:
        print("* [[{}]]".format(talk))

if __name__ == "__main__":
    import ws.config

    argparser = ws.config.getArgParser(description="Find closed discussions")
    API.set_argparser(argparser)
    Database.set_argparser(argparser)

    args = ws.config.parse_args()

    api = API.from_argparser(args)
    db = Database.from_argparser(args)

    main(api, db)
