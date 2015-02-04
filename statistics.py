#! /usr/bin/env python3

import os.path
import time
import datetime
import re
import sys
import argparse

import mwparserfromhell

try:
    # Optional for copying the text to the clipboard
    from tkinter import Tk
except ImportError:
    Tk = False

from MediaWiki import API
from MediaWiki.exceptions import APIError
from MediaWiki.interactive import require_login

api = API(
    "https://wiki.archlinux.org/api.php",
    cookie_file=os.path.expanduser("~/.cache/ArchWiki.cookie"),
    ssl_verify=True
)


class Statistics:
    """
    The whole statistics page.
    """
    PAGE = "ArchWiki:Statistics"
    SUMMARY = "automatic update"

    def __init__(self):
        self._parse_cli_args()

        if not self.cliargs.anonymous:
            require_login(api)

        self._parse_page()
        self._compose_page()
        sys.exit(self._output_page())

    def _parse_cli_args(self):
        cliparser = argparse.ArgumentParser(description="Update {}".format(
                                                    self.PAGE), add_help=True)

        actions = cliparser.add_argument_group(title="actions")
        actionsg = actions.add_mutually_exclusive_group(required=True)
        actionsg.add_argument('-i', '--initialize', action='store_const',
            const=self.initialize, dest='action', help='initialize the page')
        actionsg.add_argument('-u', '--update', action='store_const',
            const=self.update, dest='action', help='update the page')

        output = cliparser.add_argument_group(title="output")
        output.add_argument('-s', '--save', action='store_true',
                        help='try to save the page (requires being logged in)')
        output.add_argument('-c', '--clipboard', action='store_true',
                        help='try to store the updated text in the clipboard')
        output.add_argument('-p', '--print', action='store_true',
                        help='print the updated text in the standard output')


        usstats = cliparser.add_argument_group(title="user statistics")
        usstats.add_argument('--us-days-span', action='store', default=30,
                    type=int, dest='us_days', metavar='N',
                    help='the time span in days (default: %(default)s)')
        usstats.add_argument('--us-min-tot-edits', action='store',
                    default=1000, type=int, dest='us_mintotedits', metavar='N',
                    help='minimum total edits for users with not enough '
                    'recent changes; if lowering the value from the previous '
                    'updates, the page must be re-initialized! '
                    '(default: %(default)s)')
        usstats.add_argument('--us-min-rec-edits', action='store',
                    default=1, type=int, dest='us_minrecedits', metavar='N',
                    help='minimum recent changes for users with not enough '
                    'total edits (default: %(default)s)')
        usstats.add_argument('--us-err-threshold', action='store', default=6,
                    type=int, dest='us_rcerrhours', metavar='N',
                    help='the maximum difference in hours allowed between the '
                    'oldest retrieved change and the old end of the time span '
                    '(default: %(default)s)')

        cliparser.add_argument('-a', '--anonymous', action='store_true',
                                    help='do not require logging in: queries '
                                            'may be limited to a lower rate')

        self.cliargs = cliparser.parse_args()

    def _parse_page(self):
        result = api.call(action="query", prop="info|revisions",
                rvprop="content|timestamp", meta="tokens", titles=self.PAGE)
        page = tuple(result["pages"].values())[0]
        self.pageid = page["pageid"]
        revision = page["revisions"][0]
        self.text = mwparserfromhell.parse(revision["*"])
        self.timestamp = revision["timestamp"]
        self.csrftoken = result["tokens"]["csrftoken"]

    def _compose_page(self):
        userstats = _UserStats(self.text, self.cliargs.anonymous,
                    self.cliargs.us_days, self.cliargs.us_mintotedits,
                    self.cliargs.us_minrecedits, self.cliargs.us_rcerrhours)

        self.cliargs.action(userstats)

    def initialize(self, userstats):
        """
        The :py:meth:`update` method relies on the page to already have some
        values. If the page is empty, this method must be run the first time,
        which will also execute the first update.
        """
        userstats.initialize()

    def update(self, userstats):
        """
        Update the statistics, assuming that there are already some values
        that can be parsed if necessary. If this is supposed to be the initial
        update of the page, you need to use :py:meth:`initialize`.
        """
        userstats.update()

    def _output_page(self):
        ret = 0

        if self.cliargs.save:
            require_login(api)

            try:
                result = api.edit(self.pageid, self.text, self.timestamp,
                                            self.SUMMARY, token=self.csrftoken)
            except APIError as err:
                print("Could not save the page ({})".format(
                                        err.args[0]["info"]), file=sys.stderr)
                ret |= 1
            else:
                if result["result"].lower() != "success":
                    print("The page was not saved correctly", file=sys.stderr)
                    ret |= 1
                else:
                    print("The page has been saved: do not forget to "
                                                    "double-check the diff")
                    ret |= 2

        if self.cliargs.clipboard or ret is False:
            if Tk:
                w = Tk()
                w.withdraw()
                w.clipboard_clear()
                w.clipboard_append(self.text)
                # The copied text is lost once the script terminates
                input("The updated page text has been copied to the "
                        "clipboard: paste it in the browser, then press any "
                        "key to continue")
                w.destroy()

                ret |= 2
            else:
                print("It has not been possible to copy the updated text to "
                                            "the clipboard", file=sys.stderr)
                ret |= 1

        # If no other action was chosen, always print the output, so that all
        # the effort doesn't go wasted
        if self.cliargs.print or ret == 0:
            print(self.text)

        return ret & 1


class _UserStats:
    """
    User statistics.
    """
    INTRO = ("\n\nThis table shows the {} users with at least {} edits in "
            "total, combined with the {} users who made at least {} {} "
            "between {} and {} (00:00 UTC), for a total of {} users.\n\n")
    FIELDS = ("User", "Recent", "Total", "Registration", "Groups")
    GRPTRANSL = {
        "*": "",
        "autoconfirmed": "",
        "user": "",
        "bureaucrat": "[[ArchWiki:Bureaucrats|bureaucrat]], ",
        "sysop": "[[ArchWiki:Administrators|administrator]], ",
        "maintainer": "[[ArchWiki:Maintainers|maintainer]], ",
        "bot": "[[ArchWiki:Bots|bot]], ",
    }

    def __init__(self, text, is_anonymous, days, mintotedits, minrecedits,
                                                                rcerrhours):
        self.text = text.get_sections(matches="User statistics", flat=True,
                                include_lead=False, include_headings=False)[0]

        if is_anonymous:
            self.AULIMIT = 500
            self.ULIMIT = 50
            self.RCLIMIT = 500
        else:
            self.AULIMIT = 5000
            self.ULIMIT = 500
            self.RCLIMIT = 5000

        self.TIMESPAN = days * 86400
        self.CELLSN = len(self. FIELDS)
        self.MINTOTEDITS = mintotedits
        self.MINRECEDITS = minrecedits
        self.RCERRORHOURS = rcerrhours

    def initialize(self):
        self.users = {}

        for user in api.list(action="query", list="allusers",
                            aulimit=self.AULIMIT,
                            auprop="groups|editcount|registration",
                            auwitheditsonly="1"):
            if user["editcount"] >= self.MINTOTEDITS:
                name = self._format_name(user["name"])
                self.users[name] = {}
                self.users[name]["recenteditcount"] = 0
                self.users[name]["editcount"] = user["editcount"]
                self.users[name]["registration"] = self._format_registration(
                                                        user["registration"])
                self.users[name]["groups"] = self._format_groups(
                                                        user["groups"])

        self._do_update()

    def update(self):
        rowre = re.compile("^\|\-+\s*\n((?:.+\n){" +
                                str(self.CELLSN) + "})", flags=re.MULTILINE)
        cellre = re.compile("^\|\s*(.*?)$", flags=re.MULTILINE)
        self.users = {}

        for row in re.finditer(rowre, str(self.text)):
            cells = re.finditer(cellre, row.group(1))

            name = next(cells).group(1)
            # Ignore the recent edits
            next(cells)
            editcount = int(next(cells).group(1))

            if editcount >= self.MINTOTEDITS:
                self.users[name] = {}
                # The recent edits must be reset in any case
                self.users[name]["recenteditcount"] = 0
                self.users[name]["editcount"] = editcount
                self.users[name]["registration"] = next(cells).group(1)
                self.users[name]["groups"] = next(cells).group(1)

        self._do_update()

    @staticmethod
    def _format_name(name):
        return "[[User:{}|{}]]".format(name, name)

    @staticmethod
    def _format_registration(registration):
        return " ".join((registration[:10], registration[11:19]))

    @classmethod
    def _format_groups(cls, groups):
        fgroups = [cls.GRPTRANSL[group] for group in groups]
        fgroups.sort()
        return "".join(fgroups)[:-2]

    def _do_update(self):
        majorusersN = len(self.users)
        rcusers = self._find_active_users()
        activeusersN = len(rcusers)
        self._update_users_info(rcusers)
        rows = self._compose_rows()
        totalusersN = len(rows)
        self._compose_table(rows, majorusersN, activeusersN, totalusersN)

    def _find_active_users(self):
        today = int(time.time()) // 86400 * 86400
        firstday = today - self.TIMESPAN
        rc = api.list(action="query", list="recentchanges", rcstart=today,
                        rcend=firstday, rctype="edit",
                        rcprop="user|timestamp", rclimit=self.RCLIMIT)

        users = {}

        for change in rc:
            try:
                users[change["user"]] += 1
            except KeyError:
                users[change["user"]] = 1

        # Oldest retrieved timestamp
        oldestchange = datetime.datetime.strptime(change["timestamp"],
                                                        "%Y-%m-%dT%H:%M:%SZ")
        self.date = datetime.datetime.utcfromtimestamp(today)
        self.firstdate = datetime.datetime.utcfromtimestamp(firstday)
        hours = datetime.timedelta(hours=self.RCERRORHOURS)

        # Items in the recentchanges table are periodically purged according to
        # http://www.mediawiki.org/wiki/Manual:$wgRCMaxAge
        # By default the max age is 13 weeks: if a larger timespan is requested
        # here, it's very important to warn that the changes are not available
        if oldestchange - self.firstdate > hours:
            raise ShortRecentChangesError()

        return users

    def _update_users_info(self, rcusers):
        groupedusers = (tuple(rcusers.keys())[i:i+self.ULIMIT]
                                for i in range(0, len(rcusers), self.ULIMIT))

        for usersgroup in groupedusers:
            for user in api.list(action="query", list="users",
                                    usprop="groups|editcount|registration",
                                    ususers="|".join(usersgroup)):
                recenteditcount = rcusers[user["name"]]
                editcount = user["editcount"]

                # Test self.MINTOTEDITS also here, because there may be users
                # who've passed the limit since the last update
                if recenteditcount >= self.MINRECEDITS or \
                                                editcount >= self.MINTOTEDITS:
                    self.users[self._format_name(user["name"])] = {
                        "recenteditcount": recenteditcount,
                        "editcount": editcount,
                        "registration": self._format_registration(
                                                        user["registration"]),
                        "groups": self._format_groups(user["groups"]),
                    }

    def _compose_rows(self):
        rows = []

        for name in self.users:
            info = self.users[name]
            rows.append((name,
                        info["recenteditcount"],
                        info["editcount"],
                        info["registration"],
                        info["groups"]))

        # Tertiary key (registration date, ascending)
        rows.sort(key=lambda item: item[3])
        # Secondary key (edit count, descending)
        rows.sort(key=lambda item: item[2], reverse=True)
        # Primary key (recent edits, descending)
        rows.sort(key=lambda item: item[1], reverse=True)

        return rows

    def _compose_table(self, rows, majorusersN, activeusersN, totalusersN):
        newtext = (self.INTRO).format(majorusersN, self.MINTOTEDITS,
                                activeusersN, self.MINRECEDITS,
                                "edits" if self.MINRECEDITS > 1 else "edit",
                                self.firstdate.strftime("%Y-%m-%d"),
                                self.date.strftime("%Y-%m-%d"), totalusersN)

        header = '{{| class="wikitable sortable" border=1\n' + "! {}\n" * \
                                                                    self.CELLSN
        newtext += header.format(*self.FIELDS)
        template = "|-\n" + "| {}\n" * self.CELLSN

        for row in rows:
            newtext += template.format(*row)

        newtext += "|}\n"

        self.text.replace(self.text, newtext, recursive=False)


class StatisticsError(Exception):
    pass


class ShortRecentChangesError(StatisticsError):
    pass

if __name__ == "__main__":
    Statistics()
