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
        self._is_loggedin = None

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

        self._is_loggedin = do_login(self, username, password)
        return self._is_loggedin

    def is_loggedin(self):
        """
        Checks if the current session is authenticated.
        """
        if self._is_loggedin is None:
            data = self.call(action="query", meta="userinfo")
            self._is_loggedin = "anon" not in data["userinfo"]
        return self._is_loggedin

    def logout(self):
        """
        Logs out of the wiki.
        See `MediaWiki#API:Logout` for reference.
        
        :returns: True

        .. _`MediaWiki#API:Logout`: https://www.mediawiki.org/wiki/API:Logout
        """
        self.call(action="logout")
        return True


    def query_continue(self, params=None, **kwargs):
        """
        Generator for MediaWiki's query-continue feature.
        ref: https://www.mediawiki.org/wiki/API:Query#Continuing_queries

        :param params: same as :py:func:`Connection.call`, but ``action``
                is always set to ``"query"`` and ``"continue"`` to ``""``
        :param kwargs: same as :py:func:`Connection.call`
        :yields: "query" part of the API response
        """
        if params is None:
            params = kwargs
        elif not isinstance(params, dict):
            raise ValueError("params must be dict or None")
        else:
            # we will need to modify the data in dict so let's create copy
            params = params.copy()

        params["action"] = "query"
        params["continue"] = ""

        while True:
            result = self.call(params, expand_result=False)
            if "query" in result:
                yield result["query"]
            if "continue" not in result:
                break
            params.update(result["continue"])

    def generator(self, params=None, **kwargs):
        """
        Interface to API:Generators, conveniently implemented as Python generator.

        :param params: same as :py:func:`API.query_continue`
        :param kwargs: same as :py:func:`API.query_continue`
        :yields: from "pages" part of the API response
        """
        # TODO: check if "generator" param is passed?
        for snippet in self.query_continue(params, **kwargs):
            # API generator returns dict !!!
            # for example:  snippet === {"pages":
            #       {"9693": {"title": "Page title", "ns": 0, "pageid": "9693"},
            #        "1165", {"title": ...
            for _, page in snippet["pages"].items():
                yield page

    def list(self, params=None, **kwargs):
        """
        Interface to API:Lists, implemented as Python generator.

        Parameter ``list`` must be supplied.

        :param params: same as :py:func:`API.query_continue`
        :param kwargs: same as :py:func:`API.query_continue`
        :yields: from ``list`` part of the API response
        """
        list_ = kwargs.get("list") if params is None else params.get("list")
        if list_ is None:
            raise ValueError("param 'list' must be supplied")

        for snippet in self.query_continue(params, **kwargs):
            # API list returns list !!!
            # example for list="allpages":  snippet === {"allpages":
            #       [{"title": "Page title", "ns": 0, "pageid": "9693"},
            #        {"title": ...
            yield from snippet[list_]
