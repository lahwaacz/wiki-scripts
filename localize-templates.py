#! /usr/bin/env python3

import os
from ws.interactive import edit_interactive
from ws.client import API
from ws.ArchWiki import lang
import mwparserfromhell as mw

dl = lambda page: lang.detect_language(page["title"])[1]
dfkw = {"format": "json", "utf8": 1, "formatversion": 2}


def ukw(kw: dict):
    """add common attribs on kw"""
    k = dfkw.copy()
    k.update(kw)
    return k


def get_templates(api: API):
    """Get templates with i18n"""   
    ret = api.list(**ukw({
        "prop": "langlinks",
        "list": "allpages",
        "lllimit": "max",
        "apnamespace": "10",
        "apfilterlanglinks": "withlanglinks",
    }))
    return (page["title"] for page in ret if dl(page) == "English")


def edit(api: API, page, templates):
    text = page["revisions"][0]["slots"]["main"]["content"]
    timestamp = page["revisions"][0]["timestamp"]
    code = mw.parse(text)
    for curTemplate in code.filter_templates():
        for template in templates:
            if curTemplate.name.matches(template[9:]):
                curTemplate.name = f"{template[9:]} ({dl(page)})"
    if __name__ == "__main__":
        edit_interactive(api, page["title"], page["pageid"], text, str(code), timestamp, "localize templates")
    else:
        api.edit(page['title'], page['pageid'], str(code), timestamp, "localize templates", bot="")
        print(f"Edited {page['title']}")


def main(api: API):
    pages: list = []
    gentmps = get_templates(api)
    tmps: list = []
    print(end=" Getting pages...\r", flush=True)
    for i, template in enumerate(gentmps):
        tmps.append(template)
        # get page content
        ret = api.query_continue(
                **ukw(
                    {
                        "generator": "embeddedin",
                        "prop": "revisions",
                        "redirects": 1,
                        "rvprop": "content|timestamp",
                        "rvslots": "main",
                        "geilimit": "max",
                        "geifilterredir": "nonredirects",
                        "geititle": template,
                    }
                )
            )
        for bn, block in enumerate(ret):
            # ^ generators just require a for loop for the blks
            for page in block["pages"]:
                # no English; no duplicates; no namespaces
                if (
                    dl(page) != "English"
                    and page not in pages
                    and ":" not in page["title"]
                ):
                    try:
                        page["revisions"][0]  # test if revisions entry exists, else KeyError
                        pages.append(page)
                        print(
                            end=f"\033[2K Getting pages... {len(pages)} done | #{i+1}: {template[9:]} | blk #{bn+1} | {page['title']}\r",
                            flush=True,
                        )
                    except KeyError:
                        break  # exit the page loop, next block
    print(f"\033[2K{len(pages)} pages retrieved")

    for page in pages:
        print(f"~~ Editing {page['title']} ~~")
        edit(api, page, tmps)


if __name__ == "__main__":
    import ws.config

    api = ws.config.object_from_argparser(API, description="Replace unlocalised templates in localised pages with the localised templates")
    main(api)
