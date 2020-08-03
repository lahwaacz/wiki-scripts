#! /usr/bin/env python3

import logging
import datetime

import requests

from .CheckerBase import localize_flag, CheckerBase
import ws.ArchWiki.lang as lang
from ws.parser_helpers.encodings import queryencode
from ws.parser_helpers.wikicode import ensure_flagged_by_template, ensure_unflagged_by_template

__all__ = ["ManTemplateChecker"]

logger = logging.getLogger(__name__)


class ManTemplateChecker(CheckerBase):
    man_url_prefix = "http://jlk.fjfi.cvut.cz/arch/manpages/man/"

    def __init__(self, api, db, *, timeout=30, max_retries=3, **kwargs):
        super().__init__(api, db)

        self.timeout = timeout
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(max_retries=max_retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self.cache_valid_urls = set()
        self.cache_invalid_urls = set()

    def update_man_template(self, wikicode, template, src_title):
        if template.name.lower() != "man":
            return
        src_lang = lang.detect_language(src_title)[1]

        now = datetime.datetime.utcnow()
        deadlink_params = [now.year, now.month, now.day]
        deadlink_params = ["{:02d}".format(i) for i in deadlink_params]

        if not template.has(1) or not template.has(2, ignore_empty=True):
            # first replace the existing template (if any) with a translated version
            flag = self.get_localized_template("Dead link", src_lang)
            localize_flag(wikicode, template, flag)
            # flag with the correct translated template
            ensure_flagged_by_template(wikicode, template, flag, *deadlink_params, overwrite_parameters=False)
            return

        url = self.man_url_prefix
        if template.has("pkg"):
            url += template.get("pkg").value.strip() + "/"
        url += queryencode(template.get(2).value.strip())
        if template.get(1).value.strip():
            url += "." + template.get(1).value.strip()
        if template.has(3):
            url += "#{}".format(queryencode(template.get(3).value.strip()))

        if template.has("url"):
            explicit_url = template.get("url").value.strip()
        else:
            explicit_url = None

        def check_url(url):
            if url.startswith("ftp://"):
                logger.error("The FTP protocol is not supported by the requests module. URL: {}".format(url))
                return True
            if url in self.cache_valid_urls:
                return True
            elif url in self.cache_invalid_urls:
                return False
            response = self.session.get(url, timeout=self.timeout)
            if response.status_code == 200:
                # heuristics to get the missing section (redirect from some_page to some_page.1)
                # WARNING: if the manual exists in multiple sections, the first one might not be the best
                if len(response.history) == 1 and response.url.startswith(url + "."):
                    # template parameter 1= should be empty
                    assert not template.has(1, ignore_empty=True)
                    template.add(1, response.url[len(url) + 1:])
                    self.cache_valid_urls.add(response.url)
                    return True
                else:
                    self.cache_valid_urls.add(url)
                    return True
            elif response.status_code >= 400:
                self.cache_invalid_urls.add(url)
                return False
            else:
                raise NotImplementedError("Unexpected status code {} for man page URL: {}".format(response.status_code, url))

        # check if the template parameters form a valid URL
        if check_url(url):
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
            if check_url(explicit_url):
                ensure_unflagged_by_template(wikicode, template, "Dead link", match_only_prefix=True)
            else:
                # first replace the existing template (if any) with a translated version
                flag = self.get_localized_template("Dead link", src_lang)
                localize_flag(wikicode, template, flag)
                # flag with the correct translated template
                ensure_flagged_by_template(wikicode, template, flag, *deadlink_params, overwrite_parameters=False)
