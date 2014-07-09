#! /usr/bin/env python3

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
            result = self.call(data)
            if result["result"] == "Success":
                return True
            elif result["result"] == "NeedToken" and not token:
                return do_login(self, username, password, result["token"])
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
        self.call(action="logout")
        return True
