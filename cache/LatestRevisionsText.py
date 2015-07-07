#! /usr/bin/env python3

import bisect

# FIXME: should be done by reorganizin the entire project
import sys
import os
sys.path.append(os.path.abspath(".."))

from . import *
from utils import list_chunks, parse_date

__all__ = ["LatestRevisionsText"]

class LatestRevisionsText(CacheDb):
    def __init__(self, api, autocommit=True):
        # needed for database initialization
        self.limit = 500 if "apihighlimits" in api.user_rights() else 50

        super().__init__(api, "LatestRevisionsText", autocommit)

    def init(self, ns=None):
        """
        :param ns: namespace index where the revisions are taken from.
                   Internally functions as the database key.
        """
        ns = ns if ns is not None else "0"

        print("Running LatestRevisionsText.init(ns=\"{}\")".format(ns))
        if self.data is None:
            self.data = {}
        self.data[ns] = []

        allpages = self.api.generator(generator="allpages", gaplimit="max", gapfilterredir="nonredirects", gapnamespace=ns, prop="info|revisions", rvprop="content")
        for page in allpages:
            try:
                db_page = self._db_bisect_find(ns, page["title"])
                db_page.update(page)
            except IndexError:
                self._db_bisect_insert(ns, page)

        if self.autocommit is True:
            self.dump()

    def update(self, ns=None):
        """
        :param ns: namespace index where the revisions are taken from.
                   Internally functions as the database key.
        """
        ns = ns if ns is not None else "0"

        if ns not in self.data:
            self.init(ns)

        print("Running LatestRevisionsText.update(ns=\"{}\")".format(ns))
        for_update = self._get_for_update(ns)
        if len(for_update) > 0:
            print("Fetching {} new revisions...".format(len(for_update)))
            for snippet in list_chunks(for_update, self.limit):
                result = self.api.call(action="query", pageids="|".join(str(pageid) for pageid in snippet), prop="info|revisions", rvprop="content")
                for page in result["pages"].values():
                    self._db_bisect_insert(ns, page)

            if self.autocommit is True:
                self.dump()

    def _get_for_update(self, ns):
        allpages = self.api.generator(generator="allpages", gaplimit="max", gapfilterredir="nonredirects", gapnamespace=ns, prop="info")

        pageids = []
        for page in allpages:
            title = page["title"]
            pageid = page["pageid"]
            try:
                db_page = self._db_bisect_find(ns, title)
            except IndexError:
                # not found in db, needs update
                pageids.append(pageid)
                continue
            timestamp = parse_date(page["touched"])
            db_timestamp = parse_date(db_page["touched"])
            if timestamp > db_timestamp:
                pageids.append(page["pageid"])
        return pageids

    def _db_bisect_find(self, ns, title):
        # use bisect for performance
        wrapped = ListOfDictsAttrWrapper(self.data[ns], "title")
        i = bisect.bisect_left(wrapped, title)
        if i != len(wrapped) and wrapped[i] == title:
            return self.data[ns][i]
        raise IndexError

    def _db_bisect_insert(self, ns, page):
        # Insert page into database to preserve ordering by title,
        # use bisect for performance.
        wrapped = ListOfDictsAttrWrapper(self.data[ns], "title")
        title = page["title"]
        i = bisect.bisect_left(wrapped, title)
        if i != len(wrapped) and wrapped[i] == title:
            self.data[ns][i] = page
        else:
            self.data[ns].insert(i, page)
