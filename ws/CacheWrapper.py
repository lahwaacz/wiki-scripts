#! /usr/bin/env python3

import ws.cache
import ws.utils

class CacheWrapper:
    def __init__(self, api, db=None, *, cache_dir=None):
        self.db = db
        self.api = api
        self.cache_dir = cache_dir

        if db is not None:
            db.sync_with_api(api)
            # TODO: sync the content of the current revisions
        elif cache_dir is not None:
            self.db = ws.cache.LatestRevisionsText(api, self.cache_dir, autocommit=False)
            # create shallow copy of the db to trigger update only the first time
            # and not at every access
            self.db_copy = {}
            for ns in self.api.site.namespaces.keys():
                if ns >= 0:
                    self.db_copy[str(ns)] = self.db[str(ns)]
            self.db.dump()
        else:
            raise NotImplementedError("Fetching from the API is not implemented yet - it would be very slow anyway.")

    def get_page_content(self, title):
        """
        :param title: an instance of :py:class:`ws.parser_helpers.title.Title`
        :raises: :py:exc:`IndexError` if the page does not exist
        :returns: the current content of the specified page
        """
        if self.db is not None:
            raise NotImplementedError("Fetching from the SQL database is not implemented yet.")
        elif self.cache_dir is not None:
            pages = self.db_copy[str(title.namespacenumber)]
            wrapped_titles = ws.utils.ListOfDictsAttrWrapper(pages, "title")
            page = ws.utils.bisect_find(pages, title.fullpagename, index_list=wrapped_titles)
            return page["revisions"][0]["*"]

    def get_page_timestamp(self, title):
        """
        :param title: an instance of :py:class:`ws.parser_helpers.title.Title`
        :raises: :py:exc:`IndexError` if the page does not exist
        :returns: the current revision timestamp of the specified page
        """
        if self.db is not None:
            raise NotImplementedError("Fetching from the SQL database is not implemented yet.")
        elif self.cache_dir is not None:
            pages = self.db_copy[str(title.namespacenumber)]
            wrapped_titles = ws.utils.ListOfDictsAttrWrapper(pages, "title")
            page = ws.utils.bisect_find(pages, title.fullpagename, index_list=wrapped_titles)
            return page["revisions"][0]["timestamp"]
