from ws.client import API
from ws.db.database import Database
from ws.grabbers import page, protected_titles, archive, revision


def main(api, db):
    page.insert(api, db)
    protected_titles.insert(api, db)
    archive.insert(api, db)
#    revision.insert(api, db)
#    revision.update(api, db)

    for item in protected_titles.select(db):
        print(item)
    revision.select(db)


if __name__ == "__main__":
    import ws.config
    import ws.logging

    argparser = ws.config.getArgParser(description="Test grabbers")
    API.set_argparser(argparser)
    Database.set_argparser(argparser)

    args = argparser.parse_args()

    # set up logging
    ws.logging.init(args)

    api = API.from_argparser(args)
    db = Database.from_argparser(args)

    main(api, db)
