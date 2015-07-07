#! /usr/bin/env python3

import itertools
import datetime
import bisect

from utils import parse_date
import cache

class Streaks:
    def __init__(self, db_allrevprops):
        """
        :param db_allrevprops: an instance of :py:class:`cache.AllRevisionsProps`
        """
        self.db = db_allrevprops
        self.streaks = None

    def recalculate(self):
        """
        Update the :py:attribute:`self.streaks` list holding information about streaks of
        each user.
        """
        # current UTC date
        utcnow = datetime.datetime.utcnow()
        today = datetime.date(utcnow.year, utcnow.month, utcnow.day)

        # sort revisions by multiple keys: 1. user, 2. timestamp
        # this way we can group the list by users and iterate through user_revisions to
        # calculate all streaks, record the longest streak and determine the current streak
        # at the end (the last calculated streak or 0)
        # NOTE: access to database triggers an update, sorted() creates a shallow copy
        revisions = sorted(self.db["revisions"], key=lambda r: (r["user"], r["timestamp"]))
        revisions_groups = itertools.groupby(revisions, key=lambda r: r["user"])
        self.streaks = []
        for user, user_revisions in revisions_groups:
            longest, current = self._calculate_streaks(user_revisions, today)
            self.streaks.append({"user": user, "longest": longest, "current": current})

    # TODO:
    #   record date of longest streak
    def _calculate_streaks(self, revisions_iterator, today):
        """
        Calculate the longest and current streak based on given user's revisions. Streaks are
        recognized based on UTC day, but edits made UTC-yesterday are counted into the current
        streak. This way running the script just after UTC midnight will not reset current
        streaks to 0.

        :param revisions_iterator: an iterator object yielding revision dictionaries for given user
        :returns: (longest, current) tuple of streak values (in days)
        """
        longest_streak = 0
        current_streak = 0

        def _streak(revision):
            """ Return streak ID number for given revision.
                Side effect: revision["timestamp"] is parsed and replaced with `datetime.date` object
            """
            ts = parse_date(revision["timestamp"])
            date = datetime.date(ts.year, ts.month, ts.day)
            revision["timestamp"] = date

            # check if new streak starts
            if _streak.prev_date is None or date - _streak.prev_date > datetime.timedelta(days=1):
                _streak.id += 1

            _streak.prev_date = date
            return _streak.id

        _streak.prev_date = None
        _streak.id = 0

        # group revisions by streaks
        streak_groups = itertools.groupby(revisions_iterator, key=_streak)

        for _, streak in streak_groups:
            streak = list(streak)
            current_streak = (streak[-1]["timestamp"] - streak[0]["timestamp"]).days + 1

            # continuously update longest streak
            if current_streak > longest_streak:
                longest_streak = current_streak

            # check if the last edit has been made on this UTC day
            if today - streak[-1]["timestamp"] > datetime.timedelta(days=1):
                current_streak = 0

        return longest_streak, current_streak

    def get_streaks(self, user):
        """
        Get the longest and current streaks for given user.

        :param user: the user name
        :returns: a ``(longest, current)`` tuple, where the ``int``s ``longest`` and ``current``
                  stand for the longest and current streak of the given user
        :raises IndexError: when an entry for ``user`` is not found in :py:attribute:`streaks`
        """
        # use bisect for performance
        wrapped = cache.ListOfDictsAttrWrapper(self.streaks, "user")
        i = bisect.bisect_left(wrapped, user)
        if i != len(user) and wrapped[i] == user:
            entry = self.streaks[i]
            return entry["longest"], entry["current"]
        raise IndexError

if __name__ == "__main__":
    # this is only for testing...
    import os.path
    from MediaWiki import API
    api_url = "https://wiki.archlinux.org/api.php"
    cookie_path = os.path.expanduser("~/.cache/ArchWiki.cookie")

    api = API(api_url, cookie_file=cookie_path, ssl_verify=True)
    db = cache.AllRevisionsProps(api)

    import operator
    from MediaWiki.wikitable import *

    s = Streaks(db)
    s.recalculate()

    igetter = operator.itemgetter("user", "current", "longest")
    fields = ["User", "Current streak", "Longest streak"]
    rows = [igetter(r) for r in s.streaks if r["longest"] > 1 or r["current"] > 1]

    # sort by 2nd column (current streak)
    rows.sort(key=lambda row: row[1], reverse=True)

    print(Wikitable.assemble(fields, rows, single_line_rows=True))
