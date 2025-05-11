import datetime

import httpx
from mwparserfromhell.nodes import Node, Template
from mwparserfromhell.wikicode import Wikicode

import ws.ArchWiki.lang as lang
from ws.parser_helpers.encodings import anchorencode, urlencode
from ws.parser_helpers.wikicode import (
    ensure_flagged_by_template,
    ensure_unflagged_by_template,
)

from .CheckerBase import get_edit_summary_tracker, localize_flag
from .ExtlinkStatusChecker import ExtlinkStatusChecker

__all__ = ["ManTemplateChecker"]


class ManTemplateChecker(ExtlinkStatusChecker):
    man_url_prefix = "https://man.archlinux.org/man/"

    def __init__(self, api, db, **kwargs):
        super().__init__(api, db, **kwargs)

    def update_man_template(
        self, wikicode: Wikicode, template: Template, src_title: str
    ) -> None:
        if template.name.lower() != "man":
            return
        src_lang = lang.detect_language(src_title)[1]

        now = datetime.datetime.now(datetime.UTC)
        deadlink_params_int = [now.year, now.month, now.day]
        deadlink_params = [f"{i:02d}" for i in deadlink_params_int]

        if not template.has(1) or not template.has(2, ignore_empty=True):
            # first replace the existing template (if any) with a translated version
            flag = self.get_localized_template("Dead link", src_lang)
            localize_flag(wikicode, template, flag)
            # flag with the correct translated template
            ensure_flagged_by_template(
                wikicode, template, flag, *deadlink_params, overwrite_parameters=False
            )
            return

        url = self.man_url_prefix
        if template.has("pkg"):
            url += template.get("pkg").value.strip() + "/"
        url += urlencode(template.get(2).value.strip())
        # template parameter 1= should be empty
        if not template.has(1, ignore_empty=True):
            response = httpx.head(url, follow_redirects=True)
            # heuristics to get the missing section (redirect from some_page to some_page.1)
            # WARNING: if the manual exists in multiple sections, the first one might not be the best
            if (
                response.status_code == 200
                and len(response.history) == 1
                and str(response.url).startswith(url + ".")
            ):
                template.add(1, str(response.url)[len(url) + 1 :])
        if template.get(1).value.strip():
            url += "." + template.get(1).value.strip()
        if template.has(3):
            url += "#{}".format(urlencode(anchorencode(template.get(3).value.strip())))

        if template.has("url"):
            explicit_url = template.get("url").value.strip()
        else:
            explicit_url = None

        # check if the template parameters form a valid URL
        if self.check_url_sync(url):
            ensure_unflagged_by_template(
                wikicode, template, "Dead link", match_only_prefix=True
            )
            # remove explicit url= parameter - not necessary
            if explicit_url is not None:
                template.remove("url")
        elif explicit_url is None:
            # first replace the existing template (if any) with a translated version
            flag = self.get_localized_template("Dead link", src_lang)
            localize_flag(wikicode, template, flag)
            # flag with the correct translated template
            ensure_flagged_by_template(
                wikicode, template, flag, *deadlink_params, overwrite_parameters=False
            )
        elif explicit_url != "":
            if self.check_url_sync(explicit_url):
                ensure_unflagged_by_template(
                    wikicode, template, "Dead link", match_only_prefix=True
                )
            else:
                # first replace the existing template (if any) with a translated version
                flag = self.get_localized_template("Dead link", src_lang)
                localize_flag(wikicode, template, flag)
                # flag with the correct translated template
                ensure_flagged_by_template(
                    wikicode,
                    template,
                    flag,
                    *deadlink_params,
                    overwrite_parameters=False,
                )

    def handle_node(
        self, src_title: str, wikicode: Wikicode, node: Node, summary_parts: list[str]
    ) -> None:
        if isinstance(node, Template):
            summary = get_edit_summary_tracker(wikicode, summary_parts)
            with summary("updated man page links"):
                self.update_man_template(wikicode, node, src_title)
