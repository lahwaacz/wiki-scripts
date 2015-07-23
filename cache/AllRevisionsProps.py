#! /usr/bin/env python3

# FIXME: should be done by reorganizin the entire project
import sys
import os
sys.path.append(os.path.abspath(".."))

from . import *
import utils

__all__ = ["AllRevisionsProps"]

class AllRevisionsProps(CacheDb):
    def __init__(self, api, autocommit=True):
        # needed for database initialization
        self.limit = 500 if "apihighlimits" in api.user_rights() else 50

        super().__init__(api, "AllRevisionsProps", autocommit)

    def init(self, key=None):
        """
        :param key: ignored
        """
        self.data = {}
        self.data["badrevids"] = []
        self.data["revisions"] = []
        self.update()

    def update(self, key=None):
        """
        :param key: ignored
        """
        # get revision IDs of first and last revision to fetch
        firstrevid = self._get_last_revid_db() + 1
        lastrevid = self._get_last_revid_api()

        if lastrevid >= firstrevid:
            self._fetch_revisions(firstrevid, lastrevid)

            self._update_timestamp()

            if self.autocommit is True:
                self.dump()

    def _get_last_revid_db(self):
        """
        Get ID of the last revision stored in the cache database.
        """
        try:
            return self.data["revisions"][-1]["revid"]
        except IndexError:
            # empty database
            return -1

    def _get_last_revid_api(self):
        """
        Get ID of the last revision on the wiki.
        """
        result = self.api.call(action="query", list="recentchanges", rcprop="ids", rctype="edit", rclimit="1")
        return result["recentchanges"][0]["revid"]

    def _fetch_revisions(self, first, last):
        """
        Fetch properties of revisions in given numeric range and save the data
        to the database.

        :param first: (int) revision ID to start fetching from
        :param last: (int) revision ID to end fetching
        """
        # not necessary to wrap in each iteration since lists are mutable
        wrapped_revids = utils.ListOfDictsAttrWrapper(self.data["revisions"], "revid")

        for snippet in utils.list_chunks(range(first, last+1), self.limit):
            print("Fetching revids %s-%s" % (snippet[0], snippet[-1]))
            revids = "|".join(str(x) for x in snippet)
            result = self.api.call(action="query", revids=revids, prop="revisions")

            badrevids = result.get("badrevids", {})
            for _, badrev in badrevids.items():
                utils.bisect_insert_or_replace(self.data["badrevids"], badrev["revid"])

            pages = result.get("pages", {})
            for _, page in pages.items():
                # Deleted pages are yielded without the "revisions" key. Deleted revisions
                # will be handled later using the badrevids.
                revisions = page.get("revisions", [])
                for r in revisions:
                    utils.bisect_insert_or_replace(self.data["revisions"], r["revid"], data_element=r, index_list=wrapped_revids)
