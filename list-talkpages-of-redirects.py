#! /usr/bin/env python3

import os.path
import re

from MediaWiki import API
from utils import *

api_url = "https://wiki.archlinux.org/api.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")

api = API(api_url, cookie_file=cookie_path, ssl_verify=True)


# get titles of all redirect pages in 'Main', 'ArchWiki' and 'Help' namespaces
redirect_titles = []
for ns in ["0", "4", "12"]:
    _pages = api.generator(generator="allpages", gaplimit="max", gapfilterredir="redirects", gapnamespace=ns)
    redirect_titles.extend([page["title"] for page in _pages])

# get titles of all pages in 'Talk', 'ArchWiki talk' and 'Help talk' namespaces
talks = []
for ns in ["1", "5", "13"]:
    # limiting to talk pages that are not redirects is also useful
#    pages = api.generator(generator="allpages", gaplimit="max", gapnamespace=ns)
    pages = api.generator(generator="allpages", gaplimit="max", gapfilterredir="nonredirects", gapnamespace=ns)
    talks.extend([page["title"] for page in pages])

# we will need to split the namespace prefix to compare pure titles across namespaces
# TODO: refactoring (this is a generic function, but needs the list of namespaces)
def detect_namespace(title):
    """ Detect namespace of a given title.
    """
    # NOTE: namespaces hardcoded for ArchWiki
    _namespaces = ['Help talk', 'Talk', 'Media', 'File', 'ArchWiki talk', 'MediaWiki', 'File talk', 'Template', 'Category talk', 'User', 'Help', 'Special', 'Category', 'Template talk', 'User talk', 'ArchWiki', 'MediaWiki talk']
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

# print talk pages associated to a redirect page
for title in sorted(redirect_titles):
    namespace, pure_title = detect_namespace(title)
    talk_prefix = namespace + " talk:" if namespace != "Main" else "Talk:"
    talk = talk_prefix + pure_title
    if talk in talks:
        print("* [[%s]]" % talk)
