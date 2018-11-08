#! /usr/bin/env python3

import datetime
import logging

from ws.client import API
from ws.interactive import require_login
from ws.autopage import AutoPage
import ws.cache

logger = logging.getLogger(__name__)

class SortMaintainers:
    edit_summary = "automatically sort members by their recent activity"

    def __init__(self, api, cache_dir, pagename, days, min_edits):
        self.api = api
        self.pagename = pagename
        self.days = days
        self.min_edits = min_edits

        self.db_userprops = ws.cache.AllUsersProps(api, cache_dir, active_days=days, round_to_midnight=True)

        # fetch recenteditcount
        self.recenteditcount = dict((user["name"], user["recenteditcount"]) for user in self.db_userprops)

    @staticmethod
    def set_argparser(argparser):
        # first try to set options for objects we depend on
        present_groups = [group.title for group in argparser._action_groups]
        if "Connection parameters" not in present_groups:
            API.set_argparser(argparser)

        argparser.add_argument("--page-name", default="ArchWiki:Maintenance Team",
                    help="the page name on the wiki to fetch and update (default: %(default)s)")
        argparser.add_argument("--days", action="store", default=30, type=int, metavar="N",
                    help="the time span in days (default: %(default)s)")
        argparser.add_argument("--min-edits", action="store", default=10, type=int, metavar="N",
                    help="minimum number of edits for moving into the \"active\" table (default: %(default)s)")

    @classmethod
    def from_argparser(klass, args, api=None):
        if api is None:
            api = API.from_argparser(args)
        return klass(api, args.cache_dir, args.page_name, args.days, args.min_edits)

    def run(self):
        require_login(self.api)

        try:
            page = AutoPage(self.api, self.pagename)
        except ValueError:
            logger.error("The page [[{}]] currently does not exist. It must be "
                  "created manually before the script can update it."
                  .format(self.pagename))
            return

        tables = page.wikicode.filter_tags(matches=lambda node: node.tag == "table", recursive=page.wikicode.RECURSE_OTHERS)
        assert len(tables) == 2
        table_active, table_inactive = tables

        # extract rows
        rows = self.extract_rows(table_active)
        rows += self.extract_rows(table_inactive)

        # sort
        def sort_key(row):
            return self._get_editcount(row), self._get_last_edit_timestamp(row)
        rows.sort(key=sort_key, reverse=True)

        # split
        rows_active = [row for row in rows if self._get_editcount(row) >= self.min_edits]
        rows_inactive = [row for row in rows if self._get_editcount(row) < self.min_edits]

        # assemble
        for row in rows_active:
            table_active.contents.append(row)
        for row in rows_inactive:
            table_inactive.contents.append(row)

        # save
        page.save(self.edit_summary, minor="1")

    @staticmethod
    def extract_rows(table):
        rows = []
        for row in table.contents.filter_tags(matches=lambda node: node.tag == "tr", recursive=False):
            rows.append(row)
            table.contents.remove(row, recursive=False)
        return rows

    def _get_user_name(self, row):
        """ Extracts user name from given table row. """
        for wikilink in row.contents.filter_wikilinks():
            title = str(wikilink.title).strip()
            if title.lower().startswith("user:"):
                _, username = title.split(":", maxsplit=1)
                username = username[:1].upper() + username[1:]
                return username
        raise Exception("Unexpected data in the table - could not find a user name in row '{}'.".format(row))

    def _get_editcount(self, row):
        username = self._get_user_name(row)
        recenteditcount = self.recenteditcount.get(username, 0)
        return recenteditcount

    def _get_last_edit_timestamp(self, row):
        username = self._get_user_name(row)
        for _, contrib in self.api.call_api(action="query", list="usercontribs", ucuser=username, ucprop="timestamp", uclimit=1).items():
            if contrib:
                contrib = contrib[0]
                return contrib["timestamp"]
        return datetime.datetime(year=1, month=1, day=1)

if __name__ == "__main__":
    import ws.config
    sort = ws.config.object_from_argparser(SortMaintainers, description="Sort members of the ArchWiki Maintenance Team by their recent activity")
    sort.run()
