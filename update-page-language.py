#! /usr/bin/env python3

import ws.ArchWiki.lang as lang
from ws.client import API
from ws.interactive import require_login


def update_page_language(api: API) -> None:
    # ensure that we are authenticated
    require_login(api)

    namespaces = [0, 4, 10, 12, 14]
    for ns in namespaces:
        for page in api.generator(
            generator="allpages", gapnamespace=ns, gaplimit="max", prop="info"
        ):
            title = page["title"]
            pagelanguage = page["pagelanguage"]

            pure, langname = lang.detect_language(title)
            langtag = lang.tag_for_langname(langname)

            if pagelanguage != langtag:
                api.set_page_language(
                    title, langtag, "update language based on the page title"
                )


if __name__ == "__main__":
    import ws.config

    api = ws.config.object_from_argparser(
        API,
        description="Updates the page language property in the wiki's database based on the ArchWiki page naming: https://wiki.archlinux.org/title/Help:I18n#Page_titles",
    )
    update_page_language(api)
