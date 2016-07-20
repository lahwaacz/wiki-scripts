#! /usr/bin/env python3

from ws.client import API
from ws.ArchWiki import lang

# return list of page titles transcluding 'title'
def get_transclusions(api, title):
    return [page["title"] for page in api.list(list="embeddedin", eilimit="max", eititle=title, einamespace=0)]

# filter list of titles by language
def filter_titles(titles, lang_subtag):
    return [title for title in titles if lang.detect_language(title)[1] == lang.langname_for_tag(lang_subtag)]

if __name__ == "__main__":
    import ws.config
    import ws.logging

    argparser = ws.config.getArgParser(description="Filter list of pages transcluding a page by language")
    API.set_argparser(argparser)

    _script = argparser.add_argument_group(title="script parameters")
    _script.add_argument("--title", required=True,
            help="title of the transcluded page (must include the \"Template:\" prefix when it is a template)")
    _script.add_argument("--lang", choices=lang.get_internal_tags(), default="en", metavar="SUBTAG",
            help="language subtag for the filter (choices are: %(choices)s)")
    _script.add_argument("--wikify", action="store_true",
            help="use MediaWiki syntax to format a list")
    _script.add_argument("--stats", action="store_true",
            help="print some statistics")

    args = argparser.parse_args()

    # set up logging
    ws.logging.init(args)

    api = API.from_argparser(args)

    titles = get_transclusions(api, args.title)
    titles.sort()
    filtered = filter_titles(titles, args.lang)

    if args.wikify:
        for title in filtered:
            print("* [[%s]]" % title)
    else:
        print(filtered)

    if args.stats:
        print("selected:", len(filtered))
        print("total:", len(titles))
