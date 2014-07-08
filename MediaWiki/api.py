#! /usr/bin/env python3

import requests

from .connection import Connection
from .exceptions import *

__all__ = ["API"]

class API(Connection):
    """
    Simple interface to MediaWiki's API.

    This object should implement wrappers around the 'action' parameter,
    the "public" methods are named as its possible values (login, query,
    edit, ...) and helper methods start with an underscore ('_').

    :param api_url: URL path to wiki API interface
    :param kwargs: any keyword arguments of the Connection object
    """

    def __init__(self, api_url, **kwargs):
        super().__init__(api_url, **kwargs)

    def login(self, username, password):
        """
        Logs into the wiki with username and password. Returns True on successful login.
        See `MediaWiki#API:Login` for reference.

        :param username: username to use
        :param password: password to use
        :returns: True on successful login, otherwise False

        .. _`MediaWiki#API:Login`: https://www.mediawiki.org/wiki/API:Login
        """
        def do_login(self, username, password, token=None):
            """
            Login function that handles CSRF protection, see MediaWiki bug 23076:
            https://bugzilla.wikimedia.org/show_bug.cgi?id=23076

            Returns True on successful login.

            """
            data = {
                "action": "login",
                "lgname": username,
                "lgpassword": password
            }
            if token:
                data["lgtoken"] = token
            result = self.call(query, method="POST")
            if result["login"]["result"] == "Success":
                return True
            elif result["login"]["result"] == "NeedToken" and not token:
                return do_login(self, username, password, result["login"]["token"])
            else:
                return False

        return do_login(self, username, password)

    def logout(self):
        """
        Logs out of the wiki.
        See `MediaWiki#API:Logout` for reference.
        
        :returns: True

        .. _`MediaWiki#API:Logout`: https://www.mediawiki.org/wiki/API:Logout
        """
        data = {"action": "logout"}
        self.call(data)
        return True

    def query(self, data):
        """
        Base method representing `API:Query` module. Several sub-methods are provided
        for convenience, they will start with *query_*.

        :param data: dictionary of query data, ``"action": "query"`` may not be supplied
        """
        data = data.copy()
        data["action"] = "query"
        result = self.call(data)

        if "error" in result:
            raise QueryError(result["error"])
        if "warnings" in result:
            raise QueryWarnings(result["warnings"])

        return result["query"]
