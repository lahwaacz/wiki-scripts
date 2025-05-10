#! /usr/bin/env python3

import datetime
import logging

try:
    # Optional for copying the text to the clipboard
    from tkinter import Tk
except ImportError:
    Tk = None

from ws.autopage import AutoPage
from ws.client import API, APIError
from ws.db.database import Database
from ws.interactive import require_login
from ws.statistics.UserStatsModules import UserStatsModules
from ws.wikitable import Wikitable

logger = logging.getLogger(__name__)

class Statistics:
    """
    The whole statistics page.
    """
    def __init__(self, api, db, cliargs):
        self.api = api
        self.db = db
        self.cliargs = cliargs

    @staticmethod
    def set_argparser(argparser):
        # first try to set options for objects we depend on
        present_groups = [group.title for group in argparser._action_groups]
        if "Connection parameters" not in present_groups:
            API.set_argparser(argparser)
        if "Database parameters" not in present_groups:
            Database.set_argparser(argparser)

        output = argparser.add_argument_group(title="output")
        # TODO: maybe leave only the short option to forbid configurability in config file
        output.add_argument('-s', '--save', action='store_true',
                        help='try to save the page (requires being logged in)')
        # FIXME: -c conflicts with -c/--config
#        output.add_argument('-c', '--clipboard', action='store_true',
        output.add_argument('--clipboard', action='store_true',
                        help='try to store the updated text in the clipboard')
        output.add_argument('-p', '--print', action='store_true',
                        help='print the updated text in the standard output '
                        '(this is the default output method)')

        usstats = argparser.add_argument_group(title="user statistics")
        usstats.add_argument('--us-days-span', action='store', default=30,
                    type=int, dest='us_days', metavar='N',
                    help='the time span in days (default: %(default)s)')
        usstats.add_argument('--us-min-tot-edits', action='store',
                    default=1000, type=int, dest='us_mintotedits', metavar='N',
                    help='minimum total edits for users with not enough '
                    'recent changes (default: %(default)s)')
        usstats.add_argument('--us-min-rec-edits', action='store',
                    default=1, type=int, dest='us_minrecedits', metavar='N',
                    help='minimum recent changes for users with not enough '
                    'total edits (default: %(default)s)')

        # TODO: main group for "script parameters" would be most logical, but
        #       but argparse does not display nested groups in the help page
        group = argparser.add_argument_group(title="other parameters")

        group.add_argument('-a', '--anonymous', action='store_true',
                    help='do not require logging in: queries may be limited to '
                    'a lower rate')
        # TODO: maybe leave only the short option to forbid configurability in config file
        group.add_argument('-f', '--force', action='store_true',
                    help='try to update the page even if it was last saved in '
                    'the same UTC day')
        group.add_argument('--statistics-page', default='ArchWiki:Statistics',
                    help='the page name on the wiki to fetch and update '
                    '(default: %(default)s)')
        # TODO: no idea how to forbid setting this globally in the config...
        group.add_argument('--summary', default='automatic update',
                    help='the edit summary to use when saving the page '
                    '(default: %(default)s)')

    @classmethod
    def from_argparser(klass, args, api=None, db=None):
        if api is None:
            api = API.from_argparser(args)
        if db is None:
            db = Database.from_argparser(args)
        return klass(api, db, args)

    def run(self):
        if not self.cliargs.anonymous:
            require_login(self.api)

        # synchronize the database
        self.db.sync_with_api(self.api)

        try:
            self.page = AutoPage(self.api, self.cliargs.statistics_page)
        except ValueError:
            logger.error("The page [[{}]] currently does not exist. It must be "
                  "created manually before the script can update it."
                  .format(self.cliargs.statistics_page))
            return 1

        if self.cliargs.force or self.page.is_old_enough(min_interval=datetime.timedelta(days=1), strip_time=True):
            self._compose_page()
            return self._output_page()
        else:
            logger.info("The page has already been updated this UTC day")
            return 1

    def _compose_page(self):
        userstats = _UserStats(self.api, self.db, self.page,
                    self.cliargs.us_days, self.cliargs.us_mintotedits,
                    self.cliargs.us_minrecedits)
        userstats.update()

    def _output_page(self):
        ret = 0

        if self.cliargs.save:
            require_login(self.api)

            try:
                self.page.save(self.cliargs.summary, minor="1")
                logger.info("The page has been saved: do not forget to "
                            "double-check the diff")
                ret |= 2
            except APIError:
                ret |= 1

        if self.cliargs.clipboard or ret is False:
            if Tk:
                w = Tk()
                w.withdraw()
                w.clipboard_clear()
                w.clipboard_append(self.page.wikicode)
                # The copied text is lost once the script terminates
                input("The updated page text has been copied to the clipboard: "
                      "paste it in the browser, then press Enter to continue")
                w.destroy()

                ret |= 2
            else:
                logger.error("It has not been possible to copy the updated "
                             "text to the clipboard")
                ret |= 1

        # If no other action was chosen, always print the output, so that all
        # the effort doesn't go wasted
        if self.cliargs.print or ret == 0:
            print(self.page.wikicode)

        return ret & 1


class _UserStats:
    """
    User statistics.
    """
    INTRO = """\n
This table shows the {} users with at least {} edits in total, combined with \
the {} users who made at least {} {} in the {} days between {} and {} (00:00 \
UTC), for a total of {} users.

The meaning of the additional columns is:

* '''Roles''' &mdash; a human-readable representation of the most relevant \
[[ArchWiki:Access levels and roles|access levels and roles]].
* '''Recent''' &mdash; the number of edits made in the past 30 days. Includes \
only normal edits, not special actions such as moving a page.
* '''Total''' &mdash; the total number of edits made since the registration. \
Includes only normal edits (including deleted ones), special actions are not \
counted.
* '''Longest streak''' &mdash; the length of the longest recorded streak in \
days. The details for the streak are provided as tooltips.
* '''Current streak''' &mdash; the length of the last recorded streak in days. \
The details for the streak are provided as tooltips.
* '''Avg. (total)''' &mdash; the average of edits per day since the user's \
registration, calculated as the total number of edits divided by the number of \
days since the registration date until today.
* '''Avg. (active)''' &mdash; the ''active'' average of edits per day between \
the user's first and last edits, calculated as the total number of edits \
divided by the number of days between the user's first and last edits.

"""
    FIELDS = ("user", "registration", "groups", "recenteditcount", "editcount",
              "longest streak", "current streak", "totaleditsperday",
              "activeeditsperday")
    FIELDS_FORMAT = ("User", "Registration", "Roles", "Recent", "Total",
                     "Longest<br>streak", "Current<br>streak",
                     "Avg.<br>(total)", "Avg.<br>(active)")
    GRPTRANSL = {
        # Access levels
        "*": lambda groups: "",
        "autoconfirmed": lambda groups: "",
        "user": lambda groups: "",
        "checkuser": lambda groups: "",
        "bureaucrat": lambda groups: "[[ArchWiki:Bureaucrats|Bureaucrat]]",
        "sysop": lambda groups: "",
        "cosysop": lambda groups: "",
        "privileged": lambda groups: "",
        "bot": lambda groups: "[[ArchWiki:Bots|Bot]]",

        # User roles
        "maintainer": lambda groups: 'sysop' in groups and "[[ArchWiki:Administrators|Administrator]]" or "[[ArchWiki:Maintainers|Maintainer]]",
        "administrator_fellow": lambda groups: "[[ArchWiki:Administrators|Administrator Fellow]]",
        "archdev": lambda groups: "[[Roles|Developer]]",
        "archpackager": lambda groups: "[[Package Maintainer]]",
        "archstaff": lambda groups: "[[Roles|Staff]]",
        "translator": lambda groups: "[[ArchWiki:Translators|Translator]]",
    }
    STREAK_FORMAT = '<span title="{length} days, from {start} to {end} ({editcount} edits)">{length}</span>'
    REGISTRATION_FORMAT = "%Y-%m-%d %H:%M:%S"

    def __init__(self, api, db, autopage, days, mintotedits, minrecedits):
        self.api = api
        self.db = db
        self.text = autopage.wikicode.get_sections(matches="User statistics",
                    flat=True, include_lead=False, include_headings=False)[0]

        self.DAYS = days
        self.CELLSN = len(self.FIELDS)
        self.MINTOTEDITS = mintotedits
        self.MINRECEDITS = minrecedits

        self.db_userprops = list(self.db.query(list="allusers", aulimit="max", auprop={"blockinfo", "groups", "editcount", "registration"}))
        self.modules = UserStatsModules(self.db, round_to_midnight=True, active_days=days)

    def update(self):
        rows = self._compose_rows()
        majorusersN = len([1 for row in rows if row[self.FIELDS.index("editcount")] > self.MINTOTEDITS])
        activeusersN = self.modules.active_users_count()
        totalusersN = len(rows)
        self._compose_table(rows, majorusersN, activeusersN, totalusersN)

    @staticmethod
    def _format_name(name):
        return "[[User:{}|{}]]".format(name, name)

    @classmethod
    def _format_registration(cls, registration):
        if registration:
            return registration.strftime(cls.REGISTRATION_FORMAT)
        else:
            # There seems to be users without registration date (?!?) TODO: investigate
            return "-"

    @classmethod
    def _format_groups(cls, groups):
        fgroups = [cls.GRPTRANSL[group](groups) for group in groups]
        # drop empty strings
        fgroups = list(filter(bool, fgroups))
        fgroups.sort()
        return ", ".join(fgroups)

    def _compose_rows(self):
        rows = []

        for user in self.db_userprops:
            if "invalid" in user or "missing" in user:
                continue
            # Do not skip temporarily blocked users, see
            # https://wiki.archlinux.org/index.php?title=ArchWiki_talk:Statistics&oldid=794884#Blocked_users
            if "blockid" in user and user["blockexpiry"] == datetime.datetime.max.replace(tzinfo=datetime.UTC):
                continue
            name = user["name"]
            if user["editcount"] >= self.MINTOTEDITS or self.modules.recent_edit_count(name) >= self.MINRECEDITS:
                # There seems to be users without registration date (?!?) TODO: investigate
                if user["registration"]:
                    registration = user["registration"]
                else:
                    registration = None
                longest_streak, current_streak = self.modules.get_streaks(name)
                # compose row with cells ordered based on self.FIELDS
                # TODO: perhaps it would be best if Wikitable.assemble could handle list of dicts
                cells = [None] * len(self.FIELDS)
                cells[self.FIELDS.index("user")]           = self._format_name(name)
                cells[self.FIELDS.index("recenteditcount")] = self.modules.recent_edit_count(name)
                cells[self.FIELDS.index("editcount")]      = self.modules.total_edit_count(name)
                cells[self.FIELDS.index("registration")]   = self._format_registration(registration)
                cells[self.FIELDS.index("groups")]         = self._format_groups(user["groups"])
                cells[self.FIELDS.index("longest streak")] = "0" if longest_streak is None else self.STREAK_FORMAT.format(**longest_streak)
                cells[self.FIELDS.index("current streak")] = "0" if current_streak is None else self.STREAK_FORMAT.format(**current_streak)
                cells[self.FIELDS.index("totaleditsperday")] = "{:.2f}".format(self.modules.edits_per_day(name, registration))
                cells[self.FIELDS.index("activeeditsperday")] = "{:.2f}".format(self.modules.active_edits_per_day(name))
                rows.append(cells)

        # Tertiary key (registration date, ascending)
        rows.sort(key=lambda item: item[self.FIELDS.index("registration")])
        # Secondary key (edit count, descending)
        rows.sort(key=lambda item: item[self.FIELDS.index("editcount")], reverse=True)
        # Primary key (recent edits, descending)
        rows.sort(key=lambda item: item[self.FIELDS.index("recenteditcount")], reverse=True)

        return rows

    def _compose_table(self, rows, majorusersN, activeusersN, totalusersN):
        newtext = (self.INTRO).format(majorusersN, self.MINTOTEDITS,
                                activeusersN, self.MINRECEDITS,
                                "edits" if self.MINRECEDITS > 1 else "edit",
                                self.DAYS, self.modules.format_first_date(),
                                self.modules.format_last_date(), totalusersN)
        newtext += Wikitable.assemble(self.FIELDS_FORMAT, rows)
        self.text.replace(self.text, newtext, recursive=False)


if __name__ == "__main__":
    import sys

    import ws.config
    statistics = ws.config.object_from_argparser(Statistics, description="Update the statistics page on ArchWiki")
    sys.exit(statistics.run())
