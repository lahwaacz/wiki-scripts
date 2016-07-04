#! /usr/bin/env python3

import itertools

import mwparserfromhell

from ws.core import API
import ws.utils
from ws.interactive import edit_interactive
import ws.ArchWiki.lang as lang
from ws.ArchWiki.header import get_header_parts, build_header

def pages_in_namespace(api, ns):
    return api.generator(generator="allpages", gapfilterredir="nonredirects", gapnamespace=ns, gaplimit="max", prop="categories", cllimit="max", clshow="!hidden")

def fix_pages(api, pageids):
    for chunk in ws.utils.iter_chunks(pageids, api.max_ids_per_query):
        pageids = "|".join(str(pageid) for pageid in chunk)
        result = api.call_api(action="query", pageids=pageids, prop="revisions", rvprop="content|timestamp")
        pages = result["pages"]
        for page in pages.values():
            text = page["revisions"][0]["*"]
            timestamp = page["revisions"][0]["timestamp"]
            fix_categories(api, page["pageid"], page["title"], text, timestamp)

def fix_categories(api, pageid, title, text_old, timestamp):
    langname = lang.detect_language(title)[1]
    wikicode = mwparserfromhell.parse(text_old)
    parent, magics, cats, langlinks = get_header_parts(wikicode, remove_from_parent=True)

    for cat in cats:
        # get_header_parts returns list of wikicode objects, each with one node
        cat = cat.nodes[0]

        pure, ln = lang.detect_language(str(cat.title))
        if ln != langname:
            if langname == lang.get_local_language():
                cat.title = "{}".format(pure)
            else:
                cat.title = "{} ({})".format(pure, langname)

    build_header(wikicode, parent, magics, cats, langlinks)
    text_new = str(wikicode)
    if text_old != text_new:
        summary = "fix category, see [[Help:Category#i18n category name]]"
        edit_interactive(api, title, pageid, text_old, text_new, timestamp, summary, bot="")
#        self.api.edit(page["title"], pageid, text_new, timestamp, summary, bot="")

def main(api):
    pages = itertools.chain.from_iterable(pages_in_namespace(api, ns) for ns in [0, 4, 10, 12, 14])

    needs_fixing = []

    for page in pages:
        langname = lang.detect_language(page["title"])[1]
        if "categories" in page:
            for cat in page["categories"]:
                # skip root categories for non-English languages
                if page["title"] == "Category:{}".format(langname) and cat["title"] == "Category:Languages":
                    continue

                # check language
                if lang.detect_language(cat["title"])[1] != langname:
                    print("* Page [[:{}]] is categorized under wrong language: [[:{}]]".format(page["title"], cat["title"]))
                    needs_fixing.append(page["pageid"])

    fix_pages(api, needs_fixing)

if __name__ == "__main__":
    import ws.config
    api = ws.config.object_from_argparser(API, description="Check i18n rules in the content namespaces")
    main(api)
