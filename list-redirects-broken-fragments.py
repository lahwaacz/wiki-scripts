#! /usr/bin/env python3

# TODO:
#   pulling revisions from cache does not expand templates (transclusions like on List of applications)
#   finally merge into link-checker.py, broken stuff should be just reported

from ws.client import API
from ws.db.database import Database
from ws.parser_helpers.encodings import dotencode
from ws.parser_helpers.wikicode import get_section_headings, get_anchors

def valid_sectionname(db, title):
    """
    Checks if the ``sectionname`` property of given title is valid, i.e. if a
    corresponding section exists on a page with given title.

    .. note::
        Validation is limited to pages in the Main namespace for easier access
        to the cache; anchors on other pages are considered to be always valid.

    :param ws.db.database.Database db: database object
    :param title: parsed title of the wikilink to be checked
    :type title: ws.parser_helpers.title.Title
    :returns: ``True`` if the anchor corresponds to an existing section
    """
    # we can't check interwiki links
    if title.iwprefix:
        return True

    # TODO: limitation of the cache, we can easily check only the main namespace
    if title.namespace != "":
        return True

    # empty sectionname is always valid
    if title.sectionname == "":
        return True

    result = db.query(titles={title.fullpagename}, prop="latestrevisions", rvprop={"content"})
    result = list(result)
    text = result[0]["*"]

    # get list of valid anchors
    anchors = get_anchors(get_section_headings(text))

    # encode the given anchor and validate
    return dotencode(title.sectionname) in anchors

def main(api, db):
    db.sync_with_api(api)
    db.sync_latest_revisions_content(api)

    # limit to redirects pointing to the content namespaces
    redirects = api.redirects.fetch(target_namespaces=[0, 4, 12])

    for source in sorted(redirects.keys()):
        target = redirects[source]
        title = api.Title(target)

        # limit to redirects with broken fragment
        if valid_sectionname(db, title):
            continue

        print("* [[{}]] --> [[{}]]".format(source, target))

if __name__ == "__main__":
    import ws.config
    import ws.logging

    argparser = ws.config.getArgParser(description="List redirects with broken fragments")
    API.set_argparser(argparser)
    Database.set_argparser(argparser)

    args = argparser.parse_args()

    # set up logging
    ws.logging.init(args)

    api = API.from_argparser(args)
    db = Database.from_argparser(args)

    main(api, db)
