#! /usr/bin/env python3

from ws.client import API
from ws.interlanguage.Categorization import *
from ws.interlanguage.CategoryGraph import *
from ws.interlanguage.InterlanguageLinks import *

modes = ["update", "orphans"]
_modes_desc = {
    "update": "fix categorization of i18n pages, init wanted categories and update all interlanguage links",
    "orphans": "list all orphans",
}
modes_description = "The available modes are:"
for m in modes:
    modes_description += "\n- '{}': {}".format(m, _modes_desc[m])

def main(args, api):
    if args.mode == "update":
        # first fix categorization
        cat = Categorization(api)
        cat.fix_allpages()
        # init wanted categories
        cg = CategoryGraph(api)
        cg.init_wanted_categories()
        # update intelanguage links
        il = InterlanguageLinks(api)
        il.update_allpages()
    elif args.mode == "orphans":
        il = InterlanguageLinks(api)
        for title in il.find_orphans():
            print("* [[{}]]".format(title))
    else:
        raise Exception("Unknown mode: {}".format(args.mode))

if __name__ == "__main__":
    import ws.config
    import ws.logging

    argparser = ws.config.getArgParser(description="Update interlanguage links", epilog=modes_description)
    API.set_argparser(argparser)
    _group = argparser.add_argument_group("interlanguage")
    _group.add_argument("--mode", choices=modes, default="update", help="operation mode of the script")

    args = argparser.parse_args()

    # set up logging
    ws.logging.init(args)

    api = API.from_argparser(args)

    main(args, api)
