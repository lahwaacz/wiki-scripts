#! /usr/bin/env python3

import logging
import datetime

import requests
import mwparserfromhell

from .CheckerBase import get_edit_summary_tracker, localize_flag
from .ExtlinkStatusChecker import ExtlinkStatusChecker
import ws.ArchWiki.lang as lang
from ws.parser_helpers.encodings import urlencode, anchorencode
from ws.parser_helpers.wikicode import ensure_flagged_by_template, ensure_unflagged_by_template

__all__ = ["ManTemplateChecker"]

logger = logging.getLogger(__name__)


class ManTemplateChecker(ExtlinkStatusChecker):
    man_url_prefix = "https://jlk.fjfi.cvut.cz/arch/manpages/man/"

    def __init__(self, api, db, **kwargs):
        super().__init__(api, db, **kwargs)

    def update_man_template(self, wikicode, template, src_title):
        if template.name.lower() != "man":
            return
        src_lang = lang.detect_language(src_title)[1]

        now = datetime.datetime.utcnow()
        deadlink_params = [now.year, now.month, now.day]
        deadlink_params = ["{:02d}".format(i) for i in deadlink_params]

        if not template.has(1) or not template.has(2, ignore_empty=True):
            with self.lock_wikicode:
                # first replace the existing template (if any) with a translated version
                flag = self.get_localized_template("Dead link", src_lang)
                localize_flag(wikicode, template, flag)
                # flag with the correct translated template
                ensure_flagged_by_template(wikicode, template, flag, *deadlink_params, overwrite_parameters=False)
            return

        url = self.man_url_prefix
        if template.has("pkg"):
            url += template.get("pkg").value.strip() + "/"
        url += urlencode(template.get(2).value.strip())
        # template parameter 1= should be empty
        if not template.has(1, ignore_empty=True):
            response = self.session.head(url, timeout=self.timeout, allow_redirects=True)
            # heuristics to get the missing section (redirect from some_page to some_page.1)
            # WARNING: if the manual exists in multiple sections, the first one might not be the best
            if response.status_code == 200 and len(response.history) == 1 and response.url.startswith(url + "."):
                template.add(1, response.url[len(url) + 1:])
        if template.get(1).value.strip():
            url += "." + template.get(1).value.strip()
        if template.has(3):
            url += "#{}".format(urlencode(anchorencode(template.get(3).value.strip())))

        if template.has("url"):
            explicit_url = template.get("url").value.strip()
        else:
            explicit_url = None

        # check if the template parameters form a valid URL
        status = self.check_url(url)

        with self.lock_wikicode:
            if status:
                ensure_unflagged_by_template(wikicode, template, "Dead link", match_only_prefix=True)
                # remove explicit url= parameter - not necessary
                if explicit_url is not None:
                    template.remove("url")
            elif explicit_url is None:
                # first replace the existing template (if any) with a translated version
                flag = self.get_localized_template("Dead link", src_lang)
                localize_flag(wikicode, template, flag)
                # flag with the correct translated template
                ensure_flagged_by_template(wikicode, template, flag, *deadlink_params, overwrite_parameters=False)
            elif explicit_url != "":
                if self.check_url(explicit_url):
                    ensure_unflagged_by_template(wikicode, template, "Dead link", match_only_prefix=True)
                else:
                    # first replace the existing template (if any) with a translated version
                    flag = self.get_localized_template("Dead link", src_lang)
                    localize_flag(wikicode, template, flag)
                    # flag with the correct translated template
                    ensure_flagged_by_template(wikicode, template, flag, *deadlink_params, overwrite_parameters=False)

    def handle_node(self, src_title, wikicode, node, summary_parts):
        if isinstance(node, mwparserfromhell.nodes.Template):
            summary = get_edit_summary_tracker(wikicode, summary_parts)
            with summary("updated man page links"):
                self.update_man_template(wikicode, node, src_title)
