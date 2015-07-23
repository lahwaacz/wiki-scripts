#! /usr/bin/env python3

# TODO:
#   duplicated sections, e.g. fragments like #foo and #foo_2
#   dot-decoding of fragments
#   finally merge into link-checker.py, broken stuff should be just reported

import os.path
import re

from ws.core import API

api_url = "https://wiki.archlinux.org/api.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")

api = API(api_url, cookie_file=cookie_path, ssl_verify=True)


# limit to redirects pointing to the content namespaces
redirects = api.redirects_map(target_namespaces=[0, 4, 12])

# function to check if 'page' has 'section'
def has_section(page, section):
    # TODO: pulling revisions from cache would be much faster, but cache.LatestRevisionsText does not contain redirects (yet?) and does not expand templates (transclusions like on List of applications)
    result = api.call(action="query", prop="revisions", rvprop="content", rvexpandtemplates="", titles=page)
    _p = list(result["pages"].values())[0]
    text = _p["revisions"][0]["*"]

    if re.search(r"^(\=+)( *)%s( *)\1$" % re.escape(section), text, re.MULTILINE):
#        print("page '%s' has section '%s'" % (page, section))
        return True
    else:
#        print("page '%s' does not have section '%s'" % (page, section))
        return False

for source in sorted(redirects.keys()):
    target = redirects[source]

    # first limit to redirects with fragments
    if len(target.split("#", maxsplit=1)) == 1:
        continue

    # limit to redirects with broken fragment
    target, fragment = target.split("#", maxsplit=1)
    if has_section(target, fragment):
        continue

    print("* [[{}]] --> [[{}#{}]]".format(source, target, fragment))
