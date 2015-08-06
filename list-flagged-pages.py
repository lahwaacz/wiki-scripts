#! /usr/bin/env python3

import os.path

from ws.core import API
import ws.ArchWiki.lang as lang
from ws.logging import setTerminalLogging

setTerminalLogging()

api_url = "https://wiki.archlinux.org/api.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")

api = API(api_url, cookie_file=cookie_path, ssl_verify=True)

# return set of page titles transcluding 'title'
def get_transclusions(api, title):
    return set([page["title"] for page in api.list(list="embeddedin", eilimit="max", eititle=title, einamespace="0|4|12")])

# various "broken" pages
# see https://wiki.archlinux.org/index.php/ArchWiki:Requests#General_requests
accuracy = get_transclusions(api, "Template:Accuracy")
outofdate = get_transclusions(api, "Template:Out of date")
deletion = get_transclusions(api, "Template:Deletion")
expansion = get_transclusions(api, "Template:Expansion")
style = get_transclusions(api, "Template:Style")
merge = get_transclusions(api, "Template:Merge")
moveto = get_transclusions(api, "Template:Moveto")
stub = get_transclusions(api, "Template:Stub")

all_ = accuracy | outofdate | deletion | expansion | style | merge | moveto | stub

def print_heading(heading):
    print("== {} ==\n".format(heading))

# print list of links to given English titles, in alphabetical order
def print_titles(titles):
    for title in sorted(titles):
        if lang.detect_language(title)[1] == "English":
            print("* [[%s]]" % title)
    print()

# print titles based on some condition
# see Python set operations: https://docs.python.org/3.4/library/stdtypes.html#set

print_heading("Inaccurate and out of date")
print_titles(accuracy & outofdate)
print_heading("Inaccurate, no other flag")
print_titles(accuracy - outofdate - deletion - expansion - style - merge - moveto)
print_heading("Marked for deletion")
print_titles(deletion)
print_heading("Stub, no other flag")
print_titles(stub - accuracy - outofdate - deletion - expansion - style - merge - moveto)
print_heading("Flagged with any template")
print_titles(all_)
