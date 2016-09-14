#! /usr/bin/env python3

import datetime
import logging

from . import CacheDb
from .. import utils

logger = logging.getLogger(__name__)

__all__ = ["AllUsersProps"]

class AllUsersProps(CacheDb):

    #: format for MediaWiki timestamps
    mw_ts_format = "%Y-%m-%dT%H:%M:%SZ"

    def __init__(self, api, cache_dir, autocommit=True, active_days=30, round_to_midnight=False, rc_err_hours=6):
        """
        :param active_days:
            the time span in days to consider users as active
        :param round_to_midnight:
            Whether to round timestamps to midnight when fetching recent changes. This
            affects the ``"recenteditcount"`` property, but not the total ``"editcount"``,
            which reflects the state as of the last update of the cache.
        :param rc_err_hours:
            the maximum difference in hours allowed between the oldest retrieved
            recent change and the old end of the time span
        """
        self.round_to_midnight = round_to_midnight
        self.active_days = active_days
        self.rc_err_threshold = datetime.timedelta(hours=rc_err_hours)

        super().__init__(api, cache_dir, "AllUsersProps", autocommit)

    def init(self, key=None):
        """
        :param key: ignored
        """
        logger.info("Initializing AllUsersProps cache...")
        allusers = self.api.list(list="allusers", aulimit="max", auprop="blockinfo|groups|editcount|registration")
        # the generator yields data sorted by user name
        self.data = list(allusers)

        try:
            rcusers = self._find_active_users()
            self._update_recent_edit_counts(rcusers)
        except ShortRecentChangesError:
            pass

        self._update_timestamp()

        if self.autocommit is True:
            self.dump()

    def update(self, key=None):
        """
        :param key: ignored
        """
        users = self._find_changed_users()
        try:
            rcusers = self._find_active_users()
            # extend the list to update editcount for active users
            users += list(rcusers)
        except ShortRecentChangesError:
            logger.warning("The recent changes table on the wiki has been recently purged, starting from scratch. The recent edit count will not be available.")
            self.init()
            return

        if len(users) > 0:
            logger.info("Fetching properties of {} possibly modified user accounts...".format(len(users)))
            wrapped_names = utils.ListOfDictsAttrWrapper(self.data, "name")

            for snippet in utils.list_chunks(users, self.api.max_ids_per_query):
                for user in self.api.list(list="users", ususers="|".join(snippet), usprop="blockinfo|groups|editcount|registration"):
                    utils.bisect_insert_or_replace(self.data, user["name"], data_element=user, index_list=wrapped_names)

            self._update_recent_edit_counts(rcusers)

            self._update_timestamp()

            if self.autocommit is True:
                self.dump()

    # TODO: this could also be read from recent changes with rctype=log, which would save us one query
    def _find_changed_users(self):
        """
        Find users whose properties may have changed since the last update.
        Changes to edit counts are not taken into account.

        :returns: list of user names
        """
        lestart = self.timestamp.strftime(self.mw_ts_format)
        users = []
        for letype in ["newusers", "rights", "block"]:
            for user in self.api.list(list="logevents", letype=letype, lelimit="max", ledir="newer", lestart=lestart):
                # extract target user name
                username = user["title"].split(":", maxsplit=1)[1]
                users.append(username)
        return users

    def _find_active_users(self):
        """
        Find the users who were active in the last :py:attr:`active_days` days
        and count their recent edits.

        :returns: a mapping of user names to their recenteditcount
        """
        today = datetime.datetime.utcnow()
        if self.round_to_midnight:
            # round to midnight, keep the datetime.datetime type
            today = datetime.datetime(*(today.timetuple()[:3]))
        firstday = today - datetime.timedelta(days=self.active_days)

        rcstart = today.strftime(self.mw_ts_format)
        rcend = firstday.strftime(self.mw_ts_format)
        rc = self.api.list(action="query", list="recentchanges", rctype="edit", rcprop="user|timestamp", rclimit="max", rcstart=rcstart, rcend=rcend)

        rcusers = {}
        for change in rc:
            try:
                rcusers[change["user"]] += 1
            except KeyError:
                rcusers[change["user"]] = 1

        # Items in the recentchanges table are periodically purged according to
        # http://www.mediawiki.org/wiki/Manual:$wgRCMaxAge
        # By default the max age is 13 weeks: if a larger timespan is requested
        # here, it's very important to warn that the changes are not available
        oldestchange = utils.parse_date(change["timestamp"])
        if oldestchange - firstday > self.rc_err_threshold:
            raise ShortRecentChangesError()

        # save as meta data, only when not raising
        # TODO: figure out a way to transparently (de)serialize datetime.datetime objects in JSON format
        # FIXME: time is dropped when self.round_to_midnight is False (depends on the above)
        self.meta["firstdate"] = firstday.strftime("%Y-%m-%d")
        self.meta["lastdate"] = today.strftime("%Y-%m-%d")
        self.meta["activeuserscount"] = len(rcusers)

        return rcusers

    def _update_recent_edit_counts(self, rcusers):
        for user in self.data:
            # update recent edit count
            if user["name"] in rcusers:
                user["recenteditcount"] = rcusers[user["name"]]
            else:
                user["recenteditcount"] = 0

class ShortRecentChangesError(Exception):
    pass
