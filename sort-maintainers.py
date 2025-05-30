#! /usr/bin/env python3

import argparse
import datetime
import logging
from typing import Self, cast

from mwparserfromhell.nodes import Tag

from ws.autopage import AutoPage
from ws.client import API
from ws.config import ConfigurableObject
from ws.db.database import Database
from ws.interactive import require_login
from ws.parser_helpers.title import canonicalize

logger = logging.getLogger(__name__)


class SortMaintainers(ConfigurableObject):
    edit_summary = "automatically sort members by their recent activity"

    def __init__(
        self, api: API, db: Database, pagename: str, days: int, min_edits: int
    ):
        self.api = api
        self.db = db
        self.pagename = pagename
        self.days = days
        self.min_edits = min_edits

        # fetch recent changes from the recentchanges table
        # (does not include all revisions - "diffable" log events such as
        # page protection changes or page moves are omitted)
        lastday = datetime.datetime.now(datetime.UTC)
        firstday = lastday - datetime.timedelta(days=days)
        self.recent_changes = list(
            self.db.query(
                list="recentchanges",
                rctype={"edit", "new"},
                rcprop={"user", "timestamp"},
                rclimit="max",
                rcstart=lastday,
                rcend=firstday,
            )
        )

    @staticmethod
    def set_argparser(argparser: argparse.ArgumentParser) -> None:
        # first try to set options for objects we depend on
        present_groups = [group.title for group in argparser._action_groups]
        if "Connection parameters" not in present_groups:
            API.set_argparser(argparser)
        if "Database parameters" not in present_groups:
            Database.set_argparser(argparser)

        argparser.add_argument(
            "--page-name",
            default="ArchWiki:Maintenance Team",
            help="the page name on the wiki to fetch and update (default: %(default)s)",
        )
        argparser.add_argument(
            "--days",
            action="store",
            default=30,
            type=int,
            metavar="N",
            help="the time span in days (default: %(default)s)",
        )
        argparser.add_argument(
            "--min-edits",
            action="store",
            default=10,
            type=int,
            metavar="N",
            help='minimum number of edits for moving into the "active" table (default: %(default)s)',
        )

    @classmethod
    def from_argparser(
        cls: type[Self],
        args: argparse.Namespace,
        api: API | None = None,
        db: Database | None = None,
    ) -> Self:
        if api is None:
            api = API.from_argparser(args)
        if db is None:
            db = Database.from_argparser(args)
        return cls(api, db, args.page_name, args.days, args.min_edits)

    def run(self) -> None:
        require_login(self.api)

        # synchronize the database
        self.db.sync_with_api(self.api)

        try:
            page = AutoPage(self.api, self.pagename)
        except ValueError:
            logger.error(
                f"The page [[{self.pagename}]] currently does not exist. It must be "
                "created manually before the script can update it."
            )
            return

        tables = page.wikicode.filter_tags(
            matches=lambda node: node.tag == "table",
            recursive=page.wikicode.RECURSE_OTHERS,
        )
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
        rows_active = [
            row for row in rows if self._get_editcount(row) >= self.min_edits
        ]
        rows_inactive = [
            row for row in rows if self._get_editcount(row) < self.min_edits
        ]

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
        for row in table.contents.filter_tags(
            matches=lambda node: node.tag == "tr", recursive=False
        ):
            rows.append(row)
            table.contents.remove(row, recursive=False)
        return rows

    def _get_user_name(self, row: Tag) -> str:
        """Extracts user name from given table row."""
        for wikilink in row.contents.filter_wikilinks():
            title = str(wikilink.title).strip()
            if title.lower().startswith("user:"):
                _, username = title.split(":", maxsplit=1)
                return canonicalize(username)
        raise Exception(
            f"Unexpected data in the table - could not find a user name in row '{row}'."
        )

    def _get_editcount(self, row: Tag) -> int:
        username = self._get_user_name(row)
        edits = [r for r in self.recent_changes if r["user"] == username]
        return len(edits)

    def _get_last_edit_timestamp(self, row: Tag) -> datetime.datetime:
        username = self._get_user_name(row)
        for _, contrib in self.api.call_api(
            action="query",
            list="usercontribs",
            ucuser=username,
            ucprop="timestamp",
            uclimit=1,
        ).items():
            if contrib:
                contrib = contrib[0]
                return cast(datetime.datetime, contrib["timestamp"])
        return datetime.datetime(year=1, month=1, day=1, tzinfo=datetime.UTC)


if __name__ == "__main__":
    import ws.config

    sort = ws.config.object_from_argparser(
        SortMaintainers,
        description="Sort members of the ArchWiki Maintenance Team by their recent activity",
    )
    sort.run()
