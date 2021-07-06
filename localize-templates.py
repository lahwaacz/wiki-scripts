#! /usr/bin/env python3

from ws.interactive import edit_interactive
from ws.client import API
from ws.utils import dmerge
from ws.ArchWiki import lang
import mwparserfromhell

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
    print(f"Parsing '{page['title']}'...")
    text = page["revisions"][0]["slots"]["main"]["*"]
    timestamp = page["revisions"][0]["timestamp"]
    code = mwparserfromhell.parse(text)
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
    print("Getting page IDs...")
    pageids = set()
    templates = []
    for template in get_templates(api):
        templates.append(template)
        # get IDs of the pages using this template
        for page in api.generator(generator="embeddedin",
                                  geifilterredir="nonredirects",
                                  geilimit="max",
                                  geititle=template):
            if dl(page) != "English":
                pageids.add(page["pageid"])
    print(f"Fetched {len(pageids)} pages.")

    print("Getting page contents...")
    result = {}
    for chunk in api.call_api_autoiter_ids(action="query",
                                           pageids=pageids,
                                           prop="revisions",
                                           rvprop="content|timestamp",
                                           rvslots="main"):
        dmerge(chunk, result)

    pages = result["pages"]
    for page in pages.values():
        edit(api, page, templates)


if __name__ == "__main__":
    import ws.config

    api = ws.config.object_from_argparser(API, description="Replace unlocalised templates in localised pages with the localised templates")
    main(api)
