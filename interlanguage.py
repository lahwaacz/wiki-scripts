#! /usr/bin/env python3

from ws.client import API
from ws.interlanguage.Categorization import *
from ws.interlanguage.InterlanguageLinks import *

def main(args, api):
    if args.mode == "update":
        # first fix categorization
        cat = Categorization(api)
        cat.fix_allpages()
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

    argparser = ws.config.getArgParser(description="Update interlanguage links")
    API.set_argparser(argparser)
    _group = argparser.add_argument_group("interlanguage")
    _group.add_argument("--mode", choices=["update", "orphans"], default="update", help="operation mode of the script: 'update' all interlanguage links, list all 'orphans'")

    args = argparser.parse_args()

    # set up logging
    ws.logging.init(args)

    api = API.from_argparser(args)

    main(args, api)
