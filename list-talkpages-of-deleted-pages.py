#! /usr/bin/env python3

import os.path

from MediaWiki import API
from utils import *

api_url = "https://wiki.archlinux.org/api.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")

api = API(api_url, cookie_file=cookie_path, ssl_verify=True)


# get titles of all pages in 'Main', 'ArchWiki' and 'Help' namespaces
allpages = []
for ns in ["0", "4", "12"]:
    _pages = api.generator(generator="allpages", gaplimit="max", gapnamespace=ns)
    allpages.extend([page["title"] for page in _pages])

# get titles of all redirect pages in 'Talk', 'ArchWiki talk' and 'Help talk' namespaces
talks = []
for ns in ["1", "5", "13"]:
    pages = api.generator(generator="allpages", gaplimit="max", gapnamespace=ns)
    talks.extend([page["title"] for page in pages])

# we will need to split the namespace prefix to compare pure titles across namespaces
# TODO: refactoring (this is a generic function, but needs the list of namespaces)
def detect_namespace(title):
    """ Detect namespace of a given title.
    """
    # NOTE: namespaces hardcoded for ArchWiki
    _namespaces = ['Help talk', 'Talk', 'Media', 'File', 'ArchWiki talk', 'MediaWiki', 'File talk', 'Template', 'Category talk', 'User', 'Help', 'Special', 'Category', 'Template talk', 'User talk', 'ArchWiki', 'MediaWiki talk']
    try:
        _ns, _pure = title.split(":", 1)
        if _ns in _namespaces:
            return _ns, _pure
    except ValueError:
        pass
    return "Main", title

# print talk pages of deleted pages
for title in sorted(talks):
    namespace, pure_title = detect_namespace(title)
    prefix = namespace.split()[0] + ":" if namespace != "Talk" else ""
    page = prefix + pure_title
    if page not in allpages:
        print("* [[%s]]" % title)
