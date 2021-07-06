#! /usr/bin/env python3

from ws.interactive import edit_interactive
from ws.client import API
from ws.utils import dmerge
from ws.ArchWiki import lang
import mwparserfromhell


def page_language(page):
    return lang.detect_language(page["title"])[1]


def edit(api: API, page, templates):
    print(f"Parsing '{page['title']}'...")
    text = page["revisions"][0]["slots"]["main"]["*"]
    timestamp = page["revisions"][0]["timestamp"]
    code = mwparserfromhell.parse(text)
    for curTemplate in code.filter_templates():
        for template in templates:
            if curTemplate.name.matches(template[9:]):
                curTemplate.name = f"{template[9:]} ({page_language(page)})"
    if __name__ == "__main__":
        edit_interactive(api, page["title"], page["pageid"], text, str(code), timestamp, "localize templates")
    else:
        api.edit(page['title'], page['pageid'], str(code), timestamp, "localize templates", bot="")


def main(api: API):
    print("Getting page IDs...")
    pageids = set()
    templates = []
    for template in api.list(list="allpages",
                             apnamespace="10",
                             apfilterlanglinks="withlanglinks",
                             aplimit="max"):
        if page_language(template) == "English":
            templates.append(template["title"])
            # get IDs of the pages using this template
            for page in api.generator(generator="embeddedin",
                                      geifilterredir="nonredirects",
                                      geilimit="max",
                                      geititle=template["title"]):
                if page_language(page) != "English":
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
