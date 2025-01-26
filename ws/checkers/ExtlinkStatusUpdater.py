#! /usr/bin/env python3

# TODO:
# - show the status details when adding flags - otherwise it is hard to check if it is a false positive
# - handle flagging Template:man links with url= parameter properly ({{Dead link}} should not go inside Template:man)

import datetime
import logging

import mwparserfromhell
import sqlalchemy as sa

import ws.ArchWiki.lang as lang
from ws.diff import diff_highlighted
from ws.parser_helpers.encodings import urldecode
from ws.parser_helpers.wikicode import ensure_flagged_by_template, ensure_unflagged_by_template, get_parent_wikicode

from .CheckerBase import CheckerBase, get_edit_summary_tracker, localize_flag
from .ExtlinkStatusChecker import ExtlinkStatusChecker

__all__ = ["ExtlinkStatusUpdater"]

logger = logging.getLogger(__name__)


class ExtlinkStatusUpdater(CheckerBase):
    @property
    def deadlink_params(self):
        now = datetime.datetime.utcnow()
        params = [now.year, now.month, now.day]
        params = [f"{i:02d}" for i in params]
        return params

    @staticmethod
    def prepare_url(wikicode, extlink):
        """
        Prepares a URL of an external link in wikicode for checking.

        Note that this function assumes wikicode parsing without substituting templates.

        :returns: prepared URL as a :py:func:`str` or ``None`` if the URL should not be checked.
        """
        # make a copy of the URL object (the skip_style_flags parameter is False,
        # so we will also properly parse URLs terminated by a wiki markup)
        url = mwparserfromhell.parse(str(extlink.url))

        # mwparserfromhell parses free URLs immediately followed by a template argument
        # (e.g. http://domain.tld/{{{1}}}) completely as one URL, so we can use this
        # to skip partial URLs inside templates
        if url.filter_arguments(recursive=True):
            return

        # replace the {{=}} magic word
        if "{{=}}" in url:
            url.replace("{{=}}", "=")

        # mwparserfromhell parses free URLs immediately followed by a template
        # (e.g. http://domain.tld/{{Dead link|2020|02|20}}) completely as one URL,
        # so we need to split it manually
        if "{{" in str(url):
            # back up original wikicode
            text_old = str(wikicode)

            url, rest = str(url).split("{{", maxsplit=1)
            rest = "{{" + rest
            url = mwparserfromhell.parse(url)
            # find the index of the template in extlink.url.nodes
            # (note that it may be greater than 1, e.g. when there are HTML entities)
            for idx in range(len(extlink.url.nodes)):
                if "".join(str(n) for n in extlink.url.nodes[idx:]) == rest:
                    break
            assert "".join(str(n) for n in extlink.url.nodes[idx:]) == str(rest)
            # remove the template and everything after it from the extlink...
            # GOTCHA: the list shrinks during iteration, so we need to create a copy
            for node in list(extlink.url.nodes[idx:]):
                extlink.url.remove(node)
            # ...and insert it into the parent wikicode after the link
            parent = get_parent_wikicode(wikicode, extlink)
            parent.insert_after(extlink, rest)

            # make sure that this was a no-op
            text_new = str(wikicode)
            diff = diff_highlighted(text_old, text_new, "old", "new", "<utcnow>", "<utcnow>")
            assert text_old == text_new, f"failed to fix parsing of templates after URL. The diff is:\n{diff}"

        # replace HTML entities like "&#61" or "&Sigma;" with their unicode equivalents
        for entity in url.ifilter_html_entities(recursive=True):
            url.replace(entity, entity.normalize())

        return str(url)

    def check_extlink_status(self, wikicode, extlink, src_title):
        # preprocess the extlink and check if the URL is valid and checkable
        with self.lock_wikicode:
            url = self.prepare_url(wikicode, extlink)
        if url is None or ExtlinkStatusChecker.is_checkable_url(url) is False:
            return
        # apply additional normalization from ExtlinkStatusChecker
        url = str(ExtlinkStatusChecker.normalize_url(url))

        # get the result from the database
        with self.db.engine.connect() as conn:
            s = sa.select(self.db.ws_domain, self.db.ws_url_check) \
                .select_from(self.db.ws_domain.join(self.db.ws_url_check, self.db.ws_domain.c.name == self.db.ws_url_check.c.domain_name)) \
                .where(self.db.ws_url_check.c.url == url)
            result = conn.execute(s)
            link_status = result.fetchone()

        if link_status is None:
            logger.error(f"URL {url} from extlink {extlink} was not found in the ws_url_check table. This may be due to a parsing inconsistency with or without substitution of templates.")
            return

        with self.lock_wikicode:
            if link_status.result == "OK":
                # TODO: the link might still be flagged for a reason (e.g. when the server redirects to some dummy page without giving a proper status code)
                ensure_unflagged_by_template(wikicode, extlink, "Dead link", match_only_prefix=True)
            elif link_status.result == "bad":
                # prepare textual description for the flag
                if link_status.resolved is False:
                    link_status_description = "domain name not resolved"
                elif link_status.ssl_error is not None:
                    link_status_description = "SSL error"
                elif link_status.http_status is None:
                    link_status_description = link_status.text_status
                elif link_status.text_status is None:
                    link_status_description = str(link_status.http_status)
                else:
                    link_status_description = f"{link_status.http_status} ({link_status.text_status})"

                # first replace the existing template (if any) with a translated version
                flag = self.get_localized_template("Dead link", lang.detect_language(src_title)[1])
                localize_flag(wikicode, extlink, flag)

                # flag the link, but don't overwrite date and don't set status yet
                flag = ensure_flagged_by_template(wikicode, extlink, flag, *self.deadlink_params, overwrite_parameters=False)

                # overwrite by default, but skip overwriting date when the status matches
                overwrite = True
                if flag.has("status"):
                    status = flag.get("status").value
                    if str(status) == link_status_description:
                        overwrite = False
                if overwrite is True:
                    # overwrite status as well as date
                    flag.add("status", link_status_description, showkey=True)
                    flag.add("1", self.deadlink_params[0], showkey=False)
                    flag.add("2", self.deadlink_params[1], showkey=False)
                    flag.add("3", self.deadlink_params[2], showkey=False)
            else:
                # TODO: actually ask the user for manual check (good/bad/skip)
                logger.warning(f"external link {extlink} needs user check")

    def handle_node(self, src_title, wikicode, node, summary_parts):
        if isinstance(node, mwparserfromhell.nodes.ExternalLink):
            summary = get_edit_summary_tracker(wikicode, summary_parts)
            with summary("update status of external links"):
                self.check_extlink_status(wikicode, node, src_title)
