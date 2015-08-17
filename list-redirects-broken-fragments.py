#! /usr/bin/env python3

# TODO:
#   pulling revisions from cache does not expand templates (transclusions like on List of applications)
#   finally merge into link-checker.py, broken stuff should be just reported

import os.path
import re
import collections

from ws.core import API
import ws.cache
import ws.utils
from ws.parser_helpers.encodings import dotencode

# TODO: move to ws.parser_helpers
def valid_anchor(title, anchor, pages, wrapped_titles):
    """
    Checks if given anchor is valid, i.e. if a corresponding section exists on
    a page with given title.

    NOTE: validation is limited to pages in the Main namespace for easier
          access to the cache; anchors on other pages are considered to be
          always valid.

    :param title: title of the target page
    :param anchor: the section link anchor (without the ``#`` delimiter); may or
                   may not be dot-encoded
    :returns: ``True`` if the anchor corresponds to an existing section
    """
    namespace, _ = api.detect_namespace(title)
    if namespace != "":
        # not really, but causes to take no action
        return True
    page = ws.utils.bisect_find(pages, title, index_list=wrapped_titles)
    text = page["revisions"][0]["*"]

    # TODO: split to separate function
    # re.findall returns a list of tuples of the matched groups
    matches = re.findall(r"^((\=+)\s*)(.*?)(\s*(\2))$", text, flags=re.MULTILINE | re.DOTALL)
    headings = [match[2] for match in matches]

    # we need to encode the headings for comparison with the given anchor
    # because decoding the given anchor is ambiguous due to whitespace squashing
    # and the fact that the escape character itself (i.e. the dot) is not
    # encoded even when followed by two hex characters
    encoded = [dotencode(heading) for heading in headings]

    # handle equivalent headings duplicated on the page
    _counts = collections.Counter(encoded)
    for i in range(-1, -len(encoded), -1):
        enc = encoded[i]
        if _counts[enc] > 1:
            encoded[i] = enc + "_{}".format(_counts[enc])
        _counts[enc] -= 1

    # encode the given anchor and validate
    anchor = dotencode(anchor)
    return anchor in encoded

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
    ws.logging.init_from_argparser(args)
    ws.logging.setTerminalLogging()

    api = API.from_argparser(args)
    db = ws.cache.LatestRevisionsText(api, args.cache_dir)

    main(api, db)
