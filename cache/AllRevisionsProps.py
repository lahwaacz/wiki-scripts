#! /usr/bin/env python3

# FIXME: should be done by reorganizin the entire project
import sys
import os
sys.path.append(os.path.abspath(".."))

from . import *
from utils import list_chunks

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
            badrevids, revisions = self._fetch_revisions(firstrevid, lastrevid)
            self.data["badrevids"].extend(badrevids)
            self.data["revisions"].extend(revisions)

            # sort the data by revid
            self.data["badrevids"].sort(key=lambda x: int(x))
            self.data["revisions"].sort(key=lambda x: x["revid"])

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
        badrevids = []
        revisions = []

        for snippet in list_chunks(range(first, last+1), self.limit):
            print("Fetching revids %s-%s" % (snippet[0], snippet[-1]))
            revids = "|".join(str(x) for x in snippet)
            result = self.api.call(action="query", revids=revids, prop="revisions")

            if "badrevids" in result:
                badrevids.extend(result["badrevids"].keys())
            for _, page in result["pages"].items():
                # FIXME: workaround for deleted pages, probably should be solved differently
                if "revisions" in page:
                    revisions.extend(page["revisions"])

        return badrevids, revisions

