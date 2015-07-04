#! /usr/bin/env python3

import hashlib
from functools import lru_cache

from .connection import Connection
from .exceptions import *
from .rate import RateLimited

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
        See `MediaWiki#API:Login`_ for reference.

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

        # clear cache on self.is_loggedin
        self.is_loggedin.cache_clear()
        self.user_rights.cache_clear()

        return do_login(self, username, password)

    @lru_cache(maxsize=None)
    def is_loggedin(self):
        """
        Checks if the current session is authenticated.

        :returns: True if the session is authenticated
        """
        result = self.call(action="query", meta="userinfo")
        return "anon" not in result["userinfo"]

    @lru_cache(maxsize=None)
    def user_rights(self):
        """
        Returns a list of rights for the current user.

        :returns: a list of strings
        """
        result = self.call(action="query", meta="userinfo", uiprop="rights")
        return result["userinfo"]["rights"]

    def logout(self):
        """
        Logs out of the wiki.
        See `MediaWiki#API:Logout`_ for reference.

        :returns: True

        .. _`MediaWiki#API:Logout`: https://www.mediawiki.org/wiki/API:Logout
        """
        self.call(action="logout")
        return True


    @lru_cache(maxsize=None)
    def namespaces(self):
        """
        Fetch namespaces for the wiki. The results are cached so subsequent
        calls are cheap.

        :returns: mapping (dictionary) of namespace IDs to their names
        """
        result = self.call(action="query", meta="siteinfo", siprop="namespaces")
        namespaces = result["namespaces"].values()
        return dict( (ns["id"], ns["*"]) for ns in namespaces )

    def detect_namespace(self, title):
        """
        Detect namespace of a given title, useful to compare pure titles across
        namespaces.

        :param title: the full title of a wiki page
        :returns: A `(namespace, pure_title)` tuple. Underscores are replaced with
                  spaces in `namespace`, but `pure_title` corresponds to the input
                  (underscores and spaces are preserved). The main namespace is
                  identified as an empty string.
        """
        try:
            ns, pure = title.split(":", 1)
            ns = ns.replace("_", " ")
            if ns in self.namespaces():
                return ns, pure
        except ValueError:
            # ValueError is raised when unpacking fails
            pass
        return "", title


    def query_continue(self, params=None, **kwargs):
        """
        Generator for MediaWiki's query-continue feature.
        ref: https://www.mediawiki.org/wiki/API:Query#Continuing_queries

        :param params: same as :py:meth:`MediaWiki.connection.Connection.call`, but ``action``
                is always set to ``"query"`` and ``"continue"`` to ``""``
        :param kwargs: same as :py:meth:`MediaWiki.connection.Connection.call`
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

        :param params: same as :py:meth:`API.query_continue`
        :param kwargs: same as :py:meth:`API.query_continue`
        :yields: from "pages" part of the API response
        """
        # TODO: check if "generator" param is passed?
        for snippet in self.query_continue(params, **kwargs):
            # API generator returns dict !!!
            # for example:  snippet === {"pages":
            #       {"9693": {"title": "Page title", "ns": 0, "pageid": "9693"},
            #        "1165", {"title": ...
            snippet = sorted(snippet["pages"].values(), key=lambda d: d["title"])
            yield from snippet

    def list(self, params=None, **kwargs):
        """
        Interface to API:Lists, implemented as Python generator.

        Parameter ``list`` must be supplied.

        :param params: same as :py:meth:`API.query_continue`
        :param kwargs: same as :py:meth:`API.query_continue`
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

    @lru_cache(maxsize=8)
    def resolve_redirects(self, *pageids):
        """
        Resolve redirect titles according to the `MediaWiki's API`_. List of redirect
        pages must be obtained other way (for example by using
        ``generator=allpages&gapfilterredir=redirects`` query), or just use this
        method if unsure.

        :param *pageids: unpacked list of page IDs to resolve (i.e. call this method
                         as ``resolve_redirects(*list)`` or
                         ``resolve_redirects(pageid1, pageid2, ...)``)
        :returns: ``redirects`` part of the API response concatenated into one list

        .. _`MediaWiki's API`: https://www.mediawiki.org/wiki/API:Query#Resolving_redirects
        """
        # To resolve the redirects, the list of pageids must be split into chunks to
        # fit the limit for pageids= parameter. This can't be done on snippets
        # returned by API.query_continue(), because the limit for pageids is *lower*
        # than for the generator (for both normal and apihighlimits)
        #
        # See also https://wiki.archlinux.org/index.php/User:Lahwaacz/Notes#API:_resolving_redirects

        def _chunks(list_, bs):
            """ split ``list_`` into chunks of fixed length ``bs``
            """
            return (list_[i:i+bs] for i in range(0, len(list_), bs))

        # check if we have apihighlimits and set the limit accordingly
        limit = 500 if "apihighlimits" in self.user_rights() else 50

        # resolve by chunks
        redirects = []
        for snippet in _chunks(pageids, limit):
            result = self.call(action="query", redirects="", pageids="|".join(snippet))
            redirects.extend(result["redirects"])

        return redirects

    @RateLimited(1, 3)
    def edit(self, pageid, text, basetimestamp, summary, token=None, **kwargs):
        """
        Interface to `API:Edit`_. MD5 hash of the new text is computed automatically and
        added to the query. This method is rate-limited to allow 1 call per 3 seconds.

        :param pageid: page ID of the page to be edited
        :param text: new page content
        :param basetimestamp: Timestamp of the base revision (obtained through `prop=revisions&rvprop=timestamp`). Used to detect edit conflicts.
        :param summary: edit summary
        :param kwargs: Additional query parameters, see `API:Edit`_.

        .. _`API:Edit`: https://www.mediawiki.org/wiki/API:Edit
        """
        if not summary:
            raise Exception("edit summary is mandatory")

        # send text as utf-8 encoded
        text = text.encode("utf-8")

        # md5 hash is used to prevent data corruption during transfer
        h = hashlib.md5()
        h.update(text)
        md5 = h.hexdigest()

        if not token:
            token = self.call(action="query", meta="tokens")["tokens"]["csrftoken"]

        return self.call(action="edit", token=token, md5=md5, basetimestamp=basetimestamp, pageid=pageid, text=text, summary=summary, **kwargs)
