#! /usr/bin/env python3

import sys
import os.path
import re

from MediaWiki import API
from MediaWiki.interactive import require_login
from utils import *

index_url = "https://wiki.archlinux.org/index.php"
api_url = "https://wiki.archlinux.org/api.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")

# return HTML for given wiki title
def get_html(api, title):
    data = {"title": title.replace(" ", "_")}
    r = api.session.get(url=index_url, params=data)
    try:
        r.raise_for_status()
    except:
        print(title)
        raise
    return r.text

# return timestamp from the following tag contained in each ArchWiki page:
#   <!-- Saved in parser cache with key archwiki:pcache:idhash:941-0!*!*!*!*!*!* and timestamp 20140703093901
def get_parser_timestamp(html):
    regex = re.compile("^\\<\\!-- Saved in parser cache with key .* and timestamp ([0-9]+)")
    for line in html.splitlines():
        match = regex.match(line)
        if match:
            return match.group(1)
    return None

# return lastmod date from the following tag contained in each ArchWiki page:
#   <li id="lastmod"> This page was last modified on 3 July 2014, at 09:39.</li>
def get_lastmod(html):
    regex = re.compile("\\s*\\<li id\\=\"lastmod\"\\> This page was last modified on (.*)\\.\\<\\/li\\>")
    for line in html.splitlines():
        match = regex.match(line)
        if match:
            return match.group(1)
    return None

anon = API(api_url, ssl_verify=True)
auth = API(api_url, cookie_file=cookie_path, ssl_verify=True)

# require login for auth instance
require_login(auth)

# loop through all categories (note that until MW-1.23 non-existent categories are included)
for page in auth.list(list="allcategories", aclimit="max", acprop="size"):
    title = "Category:" + page["*"]
    if page["size"] == 0:
        print("'%s' does note exist" % title)
        continue
    auth_html = get_html(auth, title)
    anon_html = get_html(anon, title)
    auth_lastmod = get_lastmod(auth_html)
    anon_lastmod = get_lastmod(anon_html)
    if auth_lastmod is not None and auth_lastmod == anon_lastmod:
        print("OK    " + title)
        print("      " + auth_lastmod)
    else:
        print("WRONG " + title)
        print("    auth '%s'" % str(auth_lastmod))
        print("    anon '%s'" % str(anon_lastmod))
