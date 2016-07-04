#! /usr/bin/env python3

import os.path

from ws.core import API

api_urls = [
    "https://wiki.archlinux.org/api.php",
    "https://wiki.archlinux.de/api.php",
]
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")

for api_url in api_urls:
    api = API(api_url, cookie_file=cookie_path, ssl_verify=True)
    prefixes = set()
    for ns in api.site.namespaces:
        if ns < 0:
            continue
        for page in api.generator(generator="allpages", gaplimit="max", gapfilterredir="nonredirects", gapnamespace=ns, prop="iwlinks", iwprop="url", iwlimit="max"):
            for link in page.get("iwlinks", []):
                prefixes.add(link["prefix"])
    print("interwiki prefixes used on {}:".format(api.get_hostname()))
    print(sorted(prefixes))
