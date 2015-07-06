#! /usr/bin/env python3

from . import *

__all__ = ["AllRevisionsProps"]

class AllRevisionsProps(CacheDb):
    def __init__(self, api):
        # needed for database initialization
        self.limit = 500 if "apihighlimits" in api.user_rights() else 50

        super().__init__(api, "AllRevisionsProps")

    def init(self):
        self.data["badrevids"] = []
        self.data["revisions"] = []
        self.update()

    def update(self):
        # get revision IDs of first and last revision to fetch
        firstrevid = self._get_first_revision_id()
        lastrevid = self._get_last_revision_id()

        if lastrevid >= firstrevid:
            badrevids, revisions = self._fetch_revisions(firstrevid, lastrevid)
            self.data["badrevids"].extend(badrevids)
            self.data["revisions"].extend(revisions)

            # sort the data by revid
            self.data["badrevids"].sort(key=lambda x: int(x))
            self.data["revisions"].sort(key=lambda x: x["revid"])

            self.dump()

    def _get_first_revision_id(self):
        """
        Get first revision for the update query.
        """
        try:
            return self.data["revisions"][-1]["revid"] + 1
        except IndexError:
            # empty database
            return 0

    def _get_last_revision_id(self):
        """
        Get last revision for the update query.
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

