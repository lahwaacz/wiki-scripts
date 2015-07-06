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
    def __init__(self, api):
        # needed for database initialization
        self.limit = 500 if "apihighlimits" in api.user_rights() else 50

        super().__init__(api, "LatestRevisionsText")

    def init(self, ns="0"):
        print("Running LatestRevisionsText.init()")
        self.data = {}
        self.data[ns] = []
        allpages = self.api.generator(generator="allpages", gaplimit="max", gapfilterredir="nonredirects", gapnamespace=ns, prop="info|revisions", rvprop="content")
        for page in allpages:
            try:
                db_page = self._db_bisect_find(ns, page["title"])
                db_page.update(page)
            except IndexError:
                self._db_bisect_insert(ns, page)
        self.dump()

    def update(self, ns="0"):
        print("Running LatestRevisionsText.update()")
        for_update = self._get_for_update(ns)
        if len(for_update) > 0:
            print("Fetching {} new revisions...".format(len(for_update)))
        for snippet in list_chunks(for_update, self.limit):
            result = self.api.call(action="query", pageids="|".join(str(pageid) for pageid in snippet), prop="info|revisions", rvprop="content")
            for page in result["pages"].values():
                self._db_bisect_insert(ns, page)

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

# a list-like wrapper around list of dicts, operating on a given attribute
class ListOfDictsAttrWrapper(object):
    def __init__(self, dict_list, attr):
        self.dict_list = dict_list
        self.attr = attr
    def __getitem__(self, index):
        return self.dict_list[index][self.attr]
    def __len__(self):
        return self.dict_list.__len__()
