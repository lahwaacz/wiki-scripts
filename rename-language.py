#! /usr/bin/env python3

import logging

from ws.ArchWiki.lang import detect_language
from ws.client import API, APIError
from ws.interactive import require_login

logger = logging.getLogger(__name__)

class Renamer:
    edit_summary = "update language name ({old_lang} → {new_lang})"

    lang_map = {
        "Česky": "Čeština",
        "Indonesia": "Bahasa Indonesia",
        "Lietuviškai": "Lietuvių",
        "Slovenský": "Slovenčina",
    }

    def __init__(self, api):
        self.api = api

        # ensure that we are authenticated
        require_login(self.api)

    def check_page(self, title):
        # check the language
        base, lang = detect_language(title)
        new_lang = self.lang_map.get(lang)
        if not new_lang:
            return

        # format_title does not work when the script is run before updating the
        # interwiki table and the ws.ArchWiki.lang module
        #new_title = format_title(base, new_lang)
        if title == f"Category:{lang}":
            new_title = f"Category:{new_lang}"
        else:
            new_title = title.replace(f"({lang})", f"({new_lang})")

        summary = self.edit_summary.format(old_lang=lang, new_lang=new_lang)
        logger.info(f"Move [[{title}]] to [[{new_title}]] ({summary})")
        try:
            self.api.move(title, new_title, summary, movesubpages=False)
        except APIError:
            # skip errors
            pass

    def check_allpages(self):
        namespaces = [0, 4, 10, 12, 14]
        for ns in namespaces:
            for page in self.api.generator(generator="allpages", gaplimit="max", gapfilterredir="nonredirects", gapnamespace=ns):
                self.check_page(page["title"])

if __name__ == "__main__":
    import ws.config
    api = ws.config.object_from_argparser(API, description="Rename all pages to new language names")
    r = Renamer(api)
    r.check_allpages()
