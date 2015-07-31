#! /usr/bin/env python3

import os.path
import itertools

from ws.core import API

api_url = "https://wiki.archlinux.org/api.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")

api = API(api_url, cookie_file=cookie_path, ssl_verify=True)

def pages_in_namespace(ns):
    return api.generator(generator="allpages", gapnamespace=ns, gaplimit="max", prop="categories")

def get_user_names():
    return [user["name"] for user in api.list(list="allusers", aulimit="max")]

user_pages = itertools.chain(pages_in_namespace(2), pages_in_namespace(3))
users = get_user_names()

for page in user_pages:
    # check if corresponding user exists
    basepage = page["title"].split("/", 1)[0]
    user = basepage.split(":", 1)[1]
    if user not in users:
        print("* Page [[{}]] exists but username '{}' does not".format(page["title"], user))

    # user pages shall not be categorized
    if "categories" in page:
        print("* Page [[{}]] is categorized: {}".format(page["title"], list(cat["title"] for cat in page["categories"])))
