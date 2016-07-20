#! /usr/bin/env python3

import sys

from ws.client import API
from ws.dump import DumpGenerator

if __name__ == "__main__":
    import ws.config
    api = ws.config.object_from_argparser(API, description="Check pages in the user namespace")

    dg = DumpGenerator(api)

    # TODO: take parameters from command line
    r = dg.dump("stub/dump-test.xml", "2014-07-01T00:00:00Z")
    sys.exit(not r)
