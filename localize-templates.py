#! /usr/bin/env python3
'''
This script aims to replace unlocalised templates in localised pages with the localised templates.
'''
import os
import copy
from ws.client import API
import ws.ArchWiki.lang as lang
import mwparserfromhell as mw


localised_lang_name: str = "简体中文" # not required, can omit val; simplified Chinese (zh-Hans)
templates: list[str] = ["Translateme"]
api_url = "https://wiki.archlinux.org/api.php"
index_url = "https://wiki.arclinux.org/index.php"
cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")
session = API.make_session(ssl_verify=True,
                           cookie_file=cookie_path)


def edit(api: API, timestamp: str, text: str, page, template: str, language: str):
    code = mw.parse(text)
    for curTemplate in code.filter_templates():
        if curTemplate.name.matches(template):
            curTemplate.name = f"{template} ({language})"
    text = str(code)
    api.edit(pageid=page['pageid'], title=page['title'], basetimestamp=timestamp, text=new, summary="localize templates", bot="")
    print(f"Edited {page['title']}")


def process(template: str, language: str):
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
        if lang.detect_language(page['title'])[1] == language:
            pages.append(page)
    print("Done")

    firstRet = True
    for page in pages:
        text = ""
        try:
            if firstRet:
                text = page['revisions'][0]['slots']['main']['content']
                timestamp = page['revisions'][0]['timestamp']
            else:
                text = ret['pages'][str(page['pageid'])]['revisions'][0]['slots']['main']['*']
                timestamp = ret['pages'][str(page['pageid'])]['revisions'][0]['timestamp']
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
        edit(api, timestamps[i], text, pages[i], template, language)
    return


def main():
    if localised_lang_name:
        for template in templates:
            process(template, localised_lang_name)
        return
    for language in lang.get_language_names(): # just in case language is not specified
        for template in templates:
            process(template, language)
    return

if __name__ == '__main__':
    main()
