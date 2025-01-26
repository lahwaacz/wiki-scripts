#! /usr/bin/env python3

import ws.config
from ws.client import API

api = ws.config.object_from_argparser(API, description="Print namespace IDs and names")

for id_ in sorted(api.site.namespaces.keys()):
    ns = api.site.namespaces[id_]["*"]
    if ns == "":
        ns = "Main"
    print("  %2d -- %s" % (id_, ns))
