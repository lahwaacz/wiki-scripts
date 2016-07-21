#! /usr/bin/env python3

from ws.client import API
import ws.config
from ws.interlanguage.InterlanguageLinks import *

if __name__ == "__main__":
    api = ws.config.object_from_argparser(API, description="Update interlanguage links")
    il = InterlanguageLinks(api)
    il.update_allpages()
#    il.find_orphans()
