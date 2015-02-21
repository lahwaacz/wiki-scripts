#! /usr/bin/env python3

import os.path

from MediaWiki import API

api_url = "https://wiki.archlinux.org/api.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")

api = API(api_url, cookie_file=cookie_path, ssl_verify=True)

def get_titles_in_namespace(ns):
    return [page["title"] for page in api.generator(generator="allpages", gapnamespace=ns, gaplimit="max")]

def get_user_names():
    return [user["name"] for user in api.list(list="allusers", aulimit="max")]

user_pages = get_titles_in_namespace(2)
user_pages.extend(get_titles_in_namespace(3))
user_pages.sort()
users = get_user_names()

for page in user_pages:
    basepage = page.split("/", 1)[0]
    user = basepage.split(":", 1)[1]
    if user not in users:
        print("* Page [[{}]] exists but username '{}' does not".format(page, user))
