#! /usr/bin/env python3

from ws.core import API
import ws.config
api = ws.config.object_from_argparser(API, description="Print namespace IDs and names")

for id_ in sorted(api.site.namespaces.keys()):
    ns = api.site.namespaces[id_]
    if ns == "":
        ns = "Main"
    print("  %2d -- %s" % (id_, ns))
