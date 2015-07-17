#! /usr/bin/env python3

# FIXME: should be done by reorganizin the entire project
import sys
import os
sys.path.append(os.path.abspath(".."))

import datetime

from . import *
import utils

__all__ = ["AllUsersProps"]

class AllUsersProps(CacheDb):
    def __init__(self, api, autocommit=True):
        # TODO: this had better be specified as attribute of CacheDb, named chunk_size
        self.limit = 500 if "apihighlimits" in api.user_rights() else 50

        super().__init__(api, "AllUsersProps", autocommit)

    def init(self, key=None):
        """
        :param key: ignored
        """
        print("Initializing AllUsersProps cache...")
        allusers = self.api.list(list="allusers", aulimit="max", auprop="blockinfo|groups|editcount|registration")
        # the generator yields data sorted by user name
        self.data = list(allusers)

        self._update_timestamp()

        if self.autocommit is True:
            self.dump()

    def update(self, key=None):
        """
        :param key: ignored
        """
        users = self._find_changed_users()
        if len(users) > 0:
            print("Fetching properties of {} modified user accounts...")
            wrapped_names = utils.ListOfDictsAttrWrapper(self.data, "name")
            for snippet in utils.list_chunks(users, self.limit):
               for user in self.api.list(list="users", ususers="|".join(users), usprop="blockinfo|groups|editcount|registration"):
                   utils.bisect_insert_or_replace(self.data, user["name"], data_element=user, index_list=wrapped_names)

            self._update_timestamp()

            if self.autocommit is True:
                self.dump()

    def _find_changed_users(self):
        """
        Find users whose properties may have changed since the last update.

        :returns: list of user names
        """
        lestart = self.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
        users = []
        for letype in ["newusers", "rights", "block"]:
            for user in self.api.list(list="logevents", letype=letype, lelimit="max", ledir="newer", lestart=lestart):
                # extract target user name
                username = user["title"].split(":", maxsplit=1)[1]
                users.append(username)
        return users
