#! /usr/bin/env python3
'''
This script aims to replace unlocalised templates in localised pages with the localised templates.
'''
import os
import contextlib
from ws.client import API
import ws.ArchWiki.lang as lang
import mwparserfromhell


localised_lang_name = "简体中文" # simplified Chinese (zh-Hans)
templates = ["Translateme"]
api_url = "https://wiki.archlinux.org/api.php"
index_url = "https://wiki.arclinux.org/index.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")
session = API.make_session(
                           cookie_file=cookie_path)


def edit(api: API, timestamp: str, text: str, page, template: str):
    new = text.replace(r"{{" + template, r"{{" + template + f" ({localised_lang_name})")
    # api.edit(pageid=page['pageid'], title=page['title'], basetimestamp=timestamp, text=new, summary="localize templates", bot="")
    print(f"Edited {page['title']}")


def main(template: str):
    pages = []
    texts: list[str] = []
    timestamps: list[str] = []
    api = API(api_url, index_url, session)
    kwargs = {
        "action": "query",
        "format": "json",
        "maxlag": "100",
        "prop": "revisions",
        "continue": "",
        "generator": "embeddedin",
        "redirects": 1,
        "utf8": 1,
        "formatversion": "2",
        "rvprop": "content|timestamp",
        "rvslots": "main",
        "geititle": f"Template:{template}",
        "geifilterredir": "nonredirects",
        "geilimit": "max"
    }
    # get page content
    print(end="Calling API: query generator...", flush=True)
    ret = api.call_api(**kwargs)
    for page in ret['pages']:
        if page['title'].endswith(f" ({localised_lang_name})"):
            pages.append(page)
    print("Done")

    firstRet = True
    for page in pages:
        text = ""
        try:
            text = page['revisions'][0]['slots']['main']['content'] if firstRet else ret['pages'][str(page['pageid'])]['revisions'][0]['slots']['main']['*']
            timestamp = page['revisions'][0]['timestamp'] if firstRet else ret['pages'][str(page['pageid'])]['revisions'][0]['timestamp']
        except KeyError:
            firstRet = False
            print(end="Calling API: get content for remaining pages...", flush=True)
            ret = api.call_api(action="query", format="json", prop="revisions", rvprop="content|timestamp", rvslots="main", titles="|".join(page['title'] for page in pages))
            print("OK")
            text = ret['pages'][str(page['pageid'])]['revisions'][0]['slots']['main']['*']
            timestamp = ret['pages'][str(page['pageid'])]['revisions'][0]['timestamp']
        texts.append(text)
        timestamps.append(timestamp)
        print(f"Checked {page['title']}")

    for i, text in enumerate(texts):
        edit(api, timestamps[i], text, pages[i], template)
    

if __name__ == '__main__':
    for template in templates:
        main(template)
