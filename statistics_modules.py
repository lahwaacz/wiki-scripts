#! /usr/bin/env python3

import itertools
import datetime

import utils

class UserStatsModules:
    def __init__(self, db_allrevprops):
        """
        :param db_allrevprops: an instance of :py:class:`cache.AllRevisionsProps`
        """
        self.db = db_allrevprops

        # current UTC date
        utcnow = datetime.datetime.utcnow()
        self.today = datetime.date(utcnow.year, utcnow.month, utcnow.day)

        # sort revisions by multiple keys: 1. user, 2. timestamp
        # this way we can group the list by users and iterate through user_revisions to
        # calculate just about everything
        # NOTE: access to database triggers an update, sorted() creates a shallow copy
        revisions = sorted(self.db["revisions"], key=lambda r: (r["user"], r["timestamp"]))
        revisions_grouper = itertools.groupby(revisions, key=lambda r: r["user"])

        # a list containing revisions made by given user, sorted by timestamp
        self.revisions_groups = {}
        for user, user_revisions in revisions_grouper:
            self.revisions_groups[user] = list(user_revisions)

    def get_streaks(self, user):
        """
        Get the longest and current streaks for given user.

        Calculate the longest and current streak based on given user's revisions. Streaks are
        recognized based on UTC day, but edits made UTC-yesterday are counted into the current
        streak. This way running the script just after UTC midnight will not reset current
        streaks to 0.

        :param user: the user name
        :returns: ``(longest, current)`` tuple, where ``longest`` and ``current`` are dictionaries
                  representing the corresponding streaks. Provided information are "length" (in days),
                  "start", "end" (both as ``datetime.date`` object) and "editcount". If the last
                  recorded streak ended more than a day ago, ``current`` is ``None``. When there is
                  no streak recorded, both ``longest`` and ``current`` are ``None``.
        """
        def _streak(revision):
            """ Return streak ID number for given revision.
            """
            date = utils.parse_date(revision["timestamp"]).date()

            # check if new streak starts
            if _streak.prev_date is None or date - _streak.prev_date > datetime.timedelta(days=1):
                _streak.id += 1

            _streak.prev_date = date
            return _streak.id

        _streak.prev_date = None
        _streak.id = 0

        # group revisions by streaks
        streak_groups = itertools.groupby(self.revisions_groups[user], key=_streak)

        def _length(streak):
            """ Return the length of given streak in days.
            """
            delta = utils.parse_date(streak[-1]["timestamp"]) - utils.parse_date(streak[0]["timestamp"])
            return delta.days + 1

        # objects holding the revisions in the streak
        longest_streak = None
        current_streak = None
        # lengths
        longest_length = 0
        current_length = 0

        for _, streak in streak_groups:
            current_streak = list(streak)
            current_length = _length(current_streak)

            # continuously update longest streak
            if current_length > longest_length:
                longest_streak = current_streak
                longest_length = current_length

        # format information
        if longest_length > 0:
            longest = {
                "length": longest_length,
                "start": longest_streak[0]["timestamp"],
                "end": longest_streak[-1]["timestamp"],
                "editcount": len(longest_streak),
            }
        else:
            longest = None

        # check if the last edit has been made on this UTC day
        if self.today - utils.parse_date(current_streak[-1]["timestamp"]).date() <= datetime.timedelta(days=1):
            current = {
                "length": current_length,
                "start": current_streak[0]["timestamp"],
                "end": current_streak[-1]["timestamp"],
                "editcount": len(current_streak),
            }
        else:
            current = None

        return longest, current

    def edits_per_day(self, user, registration_timestamp):
        """
        :param user: the user name
        :param registration_timestamp:
            a :py:class`datetime.datetime` object representing the user's registration time
            or ``None`` if the registration date is not available for some reason
        :returns:
            a ``float`` value of the average edits per day since registration until today,
            or ``float('nan')`` if ``registration_timestamp`` is ``None``
        """
        if registration_timestamp is None:
            return float('nan')
        revisions = self.revisions_groups[user]
        delta = self.today - registration_timestamp.date()
        if delta.days == 0:
            return len(revisions)
        return len(revisions) / delta.days

    def active_edits_per_day(self, user):
        """
        :param user: the user name
        :returns:
            a ``float`` value of the average edits per day between the first and last edit dates
        """
        revisions = self.revisions_groups[user]
        delta = utils.parse_date(revisions[-1]["timestamp"]) - utils.parse_date(revisions[0]["timestamp"])
        if delta.days == 0:
            return len(revisions)
        return len(revisions) / delta.days

if __name__ == "__main__":
    # this is only for testing...
    import os.path
    import operator

    from MediaWiki import API
    import cache
    from MediaWiki.wikitable import *

    api_url = "https://wiki.archlinux.org/api.php"
    cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")

    api = API(api_url, cookie_file=cookie_path, ssl_verify=True)
    db = cache.AllRevisionsProps(api)

    usm = UserStatsModules(db)

    fields = ["User", "Current streak", "Longest streak", "Total avg.", "Active avg."]
    rows = []
    for user in usm.revisions_groups.keys():
        longest, current = usm.get_streaks(user)
        if longest is not None:
            longest = longest["length"]
        else:
            longest = 0
        if current is not None:
            current = current["length"]
        else:
            current = 0

        if longest > 1 or current > 1:
            rows.append((user, current, longest, usm.edits_per_day(user, None), usm.active_edits_per_day(user)))

    # sort by 2nd column (current streak), then by 3rd column (longest streak)
    rows.sort(key=lambda row: (row[1], row[2]), reverse=True)

    print(Wikitable.assemble(fields, rows, single_line_rows=True))
