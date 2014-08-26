#! /usr/bin/env python3

import os.path
import re

from MediaWiki import API
from utils import *

api_url = "https://wiki.archlinux.org/api.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")

#api = API(api_url, cookie_file=cookie_path, ssl_verify=True)
api = API(api_url, ssl_verify=True)


# first get list of pageids of redirect pages
redirect_titles = []
for ns in ["0", "4", "12"]:
    _pages = api.generator(generator="allpages", gaplimit="max", gapfilterredir="redirects", gapnamespace=ns)
    redirect_titles.extend([page["title"] for page in _pages])

# get all titles of talk pages for these namespaces
talks = []
for ns in ["1", "5", "13"]:
    pages = api.generator(generator="allpages", gaplimit="max", gapnamespace=ns)
    talks.extend([page["title"] for page in pages])

# we will need to split the namespace prefix to compare pure titles across namespaces
# TODO: refactoring (this is a generic function, but needs the list of namespaces)
def detect_namespace(title):
    """ Detect namespace of a given title.
    """
    _namespaces = ["Main", "ArchWiki", "Help"]  # FIXME: there are many more...
    pure_title = title
    detected_namespace = "Main"
    match = re.match("^((.+):)?(.+)$", title)
    ns = match.group(2)
    if ns:
        ns = ns.replace("_", " ")
        if ns in _namespaces:
            detected_namespace = ns
            pure_title = match.group(3)
    return detected_namespace, pure_title

#from pprint import pprint
#pprint(talks)

# print talk pages associated to a redirect page
for title in sorted(redirect_titles):
    namespace, pure_title = detect_namespace(title)
    talk_prefix = namespace + " talk:" if namespace != "Main" else "Talk:"
    talk = talk_prefix + pure_title
#    print("checking '%s'" % talk)
    if talk in talks:
        print("* [[%s]]" % talk)
