#! /usr/bin/env python3

# FIXME: should be done by reorganizin the entire project
import sys
import os
sys.path.append(os.path.abspath(".."))

from . import *
import utils

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

        # not necessary to wrap in each iteration since lists are mutable
        wrapped_titles = utils.ListOfDictsAttrWrapper(self.data[ns], "title")

        allpages = self.api.generator(generator="allpages", gaplimit="max", gapfilterredir="nonredirects", gapnamespace=ns, prop="info|revisions", rvprop="content")
        for page in allpages:
            # the same page may be yielded multiple times with different pieces
            # of the information, hence the db_page.update()
            try:
                db_page = utils.bisect_find(self.data[ns], page["title"], index_list=wrapped_titles)
                db_page.update(page)
            except IndexError:
                utils.bisect_insert_or_replace(self.data[ns], page["title"], data_element=page, index_list=wrapped_titles)

        self._update_timestamp()

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
            return

        print("Running LatestRevisionsText.update(ns=\"{}\")".format(ns))
        for_update = self._get_for_update(ns)
        if len(for_update) > 0:
            print("Fetching {} new revisions...".format(len(for_update)))

            # not necessary to wrap in each iteration since lists are mutable
            wrapped_titles = utils.ListOfDictsAttrWrapper(self.data[ns], "title")

            for snippet in utils.list_chunks(for_update, self.limit):
                result = self.api.call(action="query", pageids="|".join(str(pageid) for pageid in snippet), prop="info|revisions", rvprop="content")
                for page in result["pages"].values():
                    utils.bisect_insert_or_replace(self.data[ns], page["title"], data_element=page, index_list=wrapped_titles)

            self._update_timestamp()

            if self.autocommit is True:
                self.dump()

    def _get_for_update(self, ns):
        pageids = []

        # not necessary to wrap in each iteration since lists are mutable
        wrapped_titles = utils.ListOfDictsAttrWrapper(self.data[ns], "title")

        allpages = self.api.generator(generator="allpages", gaplimit="max", gapfilterredir="nonredirects", gapnamespace=ns, prop="info")
        for page in allpages:
            title = page["title"]
            pageid = page["pageid"]
            try:
                db_page = utils.bisect_find(self.data[ns], title, index_list=wrapped_titles)
                timestamp = utils.parse_date(page["touched"])
                db_timestamp = utils.parse_date(db_page["touched"])
                if timestamp > db_timestamp:
                    pageids.append(page["pageid"])
            except IndexError:
                # not found in db, needs update
                pageids.append(pageid)
        return pageids
