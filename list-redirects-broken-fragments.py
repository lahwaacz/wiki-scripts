#! /usr/bin/env python3

# TODO:
#   pulling revisions from cache does not expand templates (transclusions like on List of applications)
#   finally merge into link-checker.py, broken stuff should be just reported

from ws.core import API
import ws.cache
import ws.utils
from ws.parser_helpers.encodings import dotencode
from ws.parser_helpers.title import Title
from ws.parser_helpers.wikicode import get_section_headings, get_anchors

def valid_sectionname(title, pages, wrapped_titles):
    """
    Checks if the ``sectionname`` property of given title is valid, i.e. if a
    corresponding section exists on a page with given title.

    .. note::
        Validation is limited to pages in the Main namespace for easier access
        to the cache; anchors on other pages are considered to be always valid.

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

    page = ws.utils.bisect_find(pages, title.fullpagename, index_list=wrapped_titles)
    text = page["revisions"][0]["*"]

    # get list of valid anchors
    anchors = get_anchors(get_section_headings(text))

    # encode the given anchor and validate
    return dotencode(title.sectionname) in anchors

def main(api, db):
    # limit to redirects pointing to the content namespaces
    redirects = api.redirects_map(target_namespaces=[0, 4, 12])

    # reference to the list of pages to avoid update of the cache for each lookup
    pages = db["0"]
    wrapped_titles = ws.utils.ListOfDictsAttrWrapper(pages, "title")

    for source in sorted(redirects.keys()):
        target = redirects[source]
        title = Title(api, target)

        # limit to redirects with broken fragment
        if valid_sectionname(title, pages, wrapped_titles):
            continue

        print("* [[{}]] --> [[{}]]".format(source, target))

if __name__ == "__main__":
    import ws.config
    import ws.logging

    argparser = ws.config.getArgParser(description="List redirects with broken fragments")
    API.set_argparser(argparser)
    args = argparser.parse_args()

    # set up logging
    ws.logging.init(args)

    api = API.from_argparser(args)
    db = ws.cache.LatestRevisionsText(api, args.cache_dir)

    main(api, db)
