#! /usr/bin/env python3

# TODO:
#   pulling revisions from cache does not expand templates (transclusions like on List of applications)
#   finally merge into link-checker.py, broken stuff should be just reported

import re
import collections

from ws.core import API
import ws.cache
import ws.utils
from ws.parser_helpers.encodings import dotencode
from ws.parser_helpers.title import Title
from ws.parser_helpers.wikicode import get_anchors

# TODO: split to get_section_headings() and get_anchors() and move to
# ws.parser_helpers (without caching, title -> text)
def valid_anchor(title, anchor, pages, wrapped_titles):
    """
    Checks if given anchor is valid, i.e. if a corresponding section exists on
    a page with given title.

    .. note::
        validation is limited to pages in the Main namespace for easier access
        to the cache; anchors on other pages are considered to be always valid.

    :param title: title of the target page
    :param anchor: the section link anchor (without the ``#`` delimiter); may or
                   may not be dot-encoded
    :returns: ``True`` if the anchor corresponds to an existing section
    """
    _title = Title(api, title)
    if _title.namespace != "":
        # not really, but causes to take no action
        return True
    page = ws.utils.bisect_find(pages, title, index_list=wrapped_titles)
    text = page["revisions"][0]["*"]

    # get list of valid anchors
    anchors = get_anchors(text)

    # encode the given anchor and validate
    return dotencode(anchor) in anchors

def main(api, db):
    # limit to redirects pointing to the content namespaces
    redirects = api.redirects_map(target_namespaces=[0, 4, 12])

    # reference to the list of pages to avoid update of the cache for each lookup
    pages = db["0"]
    wrapped_titles = ws.utils.ListOfDictsAttrWrapper(pages, "title")

    for source in sorted(redirects.keys()):
        target = redirects[source]

        # first limit to redirects with fragments
        if len(target.split("#", maxsplit=1)) == 1:
            continue

        # limit to redirects with broken fragment
        target, fragment = target.split("#", maxsplit=1)
        if valid_anchor(target, fragment, pages, wrapped_titles):
            continue

        print("* [[{}]] --> [[{}#{}]]".format(source, target, fragment))

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
