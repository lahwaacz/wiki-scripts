#! /usr/bin/env python3

import hashlib
from functools import lru_cache
import logging

from ..utils import RateLimited, LazyProperty

from .connection import Connection, APIError
from .site import Site
from .user import User
from .tags import Tags
from .redirects import Redirects

logger = logging.getLogger(__name__)

__all__ = ["API", "LoginFailed"]

class API(Connection):
    """
    Simple interface to MediaWiki's API.

    :param kwargs: any keyword arguments of the Connection object
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def login(self, username, password):
        """
        Logs into the wiki with username and password. See `MediaWiki#API:Login`_
        for reference.

        :param username: username to use
        :param password: password to use
        :returns: ``True`` on successful login, otherwise raises :py:class:`LoginFailed`

        .. _`MediaWiki#API:Login`: https://www.mediawiki.org/wiki/API:Login
        """
        def do_login(self, username, password, token=None):
            """
            Login function that handles CSRF protection, see MediaWiki bug 23076:
            https://bugzilla.wikimedia.org/show_bug.cgi?id=23076

            :returns: ``True`` on successful login, otherwise ``False``
            """
            data = {
                "action": "login",
                "lgname": username,
                "lgpassword": password
            }
            if token:
                data["lgtoken"] = token
            result = self.call_api(data)
            if result["result"] == "Success":
                return True
            elif result["result"] == "NeedToken" and not token:
                return do_login(self, username, password, result["token"])
            else:
                return False

        # reset the properties related to login
        del self.user
        del self.max_ids_per_query

        status = do_login(self, username, password)
        if status is True and self.user.is_loggedin:
            return True
        logger.warn("Failed login attempt for user '{}'".format(username))
        raise LoginFailed

    def logout(self):
        """
        Logs out of the wiki.
        See `MediaWiki#API:Logout`_ for reference.

        :returns: ``True``

        .. _`MediaWiki#API:Logout`: https://www.mediawiki.org/wiki/API:Logout
        """
        self.call_api(action="logout")
        return True

    @LazyProperty
    def site(self):
        """
        A :py:class:`ws.client.site.Site` instance for the current wiki.
        """
        return Site(self)

    @LazyProperty
    def user(self):
        """
        A :py:class:`ws.client.user.User` instance for the current wiki.
        """
        return User(self)

    @LazyProperty
    def tags(self):
        """
        A :py:class:`ws.client.tags.Tags` instance for the current wiki.
        """
        return Tags(self)

    @LazyProperty
    def redirects(self):
        """
        A :py:class:`ws.client.redirects.Redirects` instance for the current wiki.
        """
        return Redirects(self)

    @LazyProperty
    def max_ids_per_query(self):
        """
        A maximum number of values that can be passed to the ``titles``,
        ``pageids`` and ``revids`` parameters of the API. It is 500 for users
        with the ``apihighlimits`` right and 50 for others. These values
        correspond to the actual limits enforced by MediaWiki.
        """
        return 500 if "apihighlimits" in self.user.rights else 50


    def query_continue(self, params=None, **kwargs):
        """
        Generator for MediaWiki's `query-continue feature`_.

        :param params:
            same as :py:meth:`ws.client.connection.Connection.call_api`, but
            ``action`` is always set to ``"query"`` and ``"continue"`` to ``""``
        :param kwargs:
            same as :py:meth:`ws.client.connection.Connection.call_api`
        :yields: from ``"query"`` part of the API response

        .. _`query-continue feature`: https://www.mediawiki.org/wiki/API:Query#Continuing_queries
        """
        if params is None:
            params = kwargs
        elif not isinstance(params, dict):
            raise ValueError("params must be dict or None")
        elif kwargs and params:
            raise ValueError("specifying 'params' and 'kwargs' at the same time is not supported")
        else:
            # create copy before adding action=query
            params = params.copy()
        params["action"] = "query"

        last_continue = {"continue": ""}

        while True:
            # clone the original params to clean up old continue params
            params_copy = params.copy()
            # and update with the last continue -- it may involve multiple params,
            # hence the clean up with params.copy()
            params_copy.update(last_continue)
            # call the API and handle the result
            result = self.call_api(params_copy, expand_result=False)
            if "query" in result:
                yield result["query"]
            if "continue" not in result:
                break
            last_continue = result["continue"]

    def generator(self, params=None, **kwargs):
        """
        Interface to API:Generators, conveniently implemented as Python
        generator.

        Parameter ``generator`` must be supplied.

        :param params: same as :py:meth:`API.query_continue`
        :param kwargs: same as :py:meth:`API.query_continue`
        :yields: from ``"pages"`` part of the API response

        When a generator is combined with props, results are split into multiple
        chunks, each providing piece of information. For exmample queries with
        "prop=revisions" and "rvprop=content" have a limit lower than the
        generator's maximum and specifying multiple props generally results in
        exceeding the value of ``$wgAPIMaxResultSize``.

        Although there is an automated query continuation via
        :py:meth:`query_continue`, the overlapping overlapping data is not
        squashed automatically in order to avoid keeping big data in memory
        (this is the point of API:Generators). As a result, a page may be
        yielded multiple times. See :py:meth:`ws.cache.LatestRevisionsText.init`
        for an example of proper handling of this case.
        """
        generator_ = kwargs.get("generator") if params is None else params.get("generator")
        if generator_ is None:
            raise ValueError("param 'generator' must be supplied")

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
        :yields: from ``"list"`` part of the API response
        """
        list_ = kwargs.get("list") if params is None else params.get("list")
        if list_ is None:
            raise ValueError("param 'list' must be supplied")

        for snippet in self.query_continue(params, **kwargs):
            if list_ == "querypage":
                # list=querypage needs special treatment, the structure is:
                #     snippet === {"querypage": {
                #         "results": [{"title": "Page title", "ns": 0, "pageid": "9693"},
                #                     {"title": ...}]
                #         "name": "Uncategorizedcategories"}, ...}
                yield from snippet[list_]["results"]
            else:
                # other list modules return entries directly in a list
                # example for list="allpages":
                #     snippet === {"allpages":
                #         [{"title": "Page title", "ns": 0, "pageid": "9693"},
                #          {"title": ...}]
                yield from snippet[list_]

    @LazyProperty
    def _csrftoken(self):
        logger.debug("Requesting new csrftoken...")
        return self.call_api(action="query", meta="tokens")["tokens"]["csrftoken"]

    def call_with_csrftoken(self, params=None, **kwargs):
        """
        A wrapper around :py:meth:`ws.client.connection.Connection.call_api` with
        automatic management of the `CSRF token`_.

        :param params: same as :py:meth:`ws.client.connection.Connection.call_api`
        :param kwargs: same as :py:meth:`ws.client.connection.Connection.call_api`
        :returns: same as :py:meth:`ws.client.connection.Connection.call_api`

        .. _`CSRF token`: https://www.mediawiki.org/wiki/API:Tokens
        """
        if params is None:
            params = kwargs
        elif not isinstance(params, dict):
            raise ValueError("params must be dict or None")
        elif kwargs and params:
            raise ValueError("specifying 'params' and 'kwargs' at the same time is not supported")
        else:
            # create copy before adding token
            params = params.copy()

        # ensure that the token is passed
        params["token"] = self._csrftoken

        # max tries
        max_retries = 2

        retries = max_retries
        while retries > 0:
            try:
                return self.call_api(params)
            except APIError as e:
                retries -= 1
                # csrftoken can be used multiple times, but expires after some time,
                # so try to get a new one *once*
                if e.server_response["code"] == "badtoken":
                    logger.debug("Got 'badtoken' error, trying to reset csrftoken [{}/{}]"
                            .format(max_retries - retries, max_retries))
                    # reset the cached csrftoken and try again
                    del self._csrftoken
                else:
                    raise

        # don't catch the exception for the last try
        return self.call_api(params)

    @RateLimited(1, 3)
    def edit(self, title, pageid, text, basetimestamp, summary, **kwargs):
        """
        Interface to `API:Edit`_. MD5 hash of the new text is computed
        automatically and added to the query. This method is rate-limited with
        the :py:class:`@RateLimited <ws.utils.rate.RateLimited>` decorator to
        allow 1 call per 3 seconds.

        :param str title: the title of the page (used only for logging)
        :param pageid: page ID of the page to be edited
        :type pageid: `str` or `int`
        :param str text: new page content
        :param str basetimestamp:
            Timestamp of the base revision (obtained through
            `prop=revisions&rvprop=timestamp`). Used to detect edit conflicts.
        :param str summary: edit summary
        :param kwargs: Additional query parameters, see `API:Edit`_.

        .. _`API:Edit`: https://www.mediawiki.org/wiki/API:Edit
        """
        if not summary:
            raise Exception("edit summary is mandatory")
        if len(summary) > 255:
            # TODO: the limit is planned to be increased since MW 1.25
            raise Exception("the edit summary is too long, maximum is 255 chars (got len('{}') == {})".format(summary, len(summary)))

        # send text as utf-8 encoded
        text = text.encode("utf-8")

        # md5 hash is used to prevent data corruption during transfer
        h = hashlib.md5()
        h.update(text)
        md5 = h.hexdigest()

        # if bot= is passed, also pass an assertion
        if "bot" in kwargs:
            kwargs["assert"] = "bot"
        else:
            # require being logged in, either as regular user or bot
            kwargs["assert"] = "user"

        # check and apply tags
        if "applychangetags" in self.user.rights and "wiki-scripts" in self.tags.applicable:
            kwargs.setdefault("tags", [])
            kwargs["tags"].append("wiki-scripts")
        elif "applychangetags" not in self.user.rights and "tags" in kwargs:
            logger.warning("Your account does not have the 'applychangetags' right, removing tags from the parameter list: {}".format(kwargs["tags"]))
            del kwargs["tags"]

        logger.info("Editing page [[{}]] ...".format(title))

        try:
            return self.call_with_csrftoken(action="edit", md5=md5, basetimestamp=basetimestamp, pageid=pageid, text=text, summary=summary, nocreate="1", **kwargs)
        except APIError as e:
            logger.error("Failed to edit page [[{}]] due to APIError (code '{}': {})".format(title, e.server_response["code"], e.server_response["info"]))
            raise

    @RateLimited(1, 10)
    def create(self, title, text, summary, **kwargs):
        """
        Specialization of :py:meth:`edit` for creating pages. The ``createonly``
        parameter is always added to the query. This method is rate-limited with
        the :py:class:`@RateLimited <ws.utils.rate.RateLimited>` decorator to
        allow 1 call per 10 seconds.

        :param str title: the title of the page to be created
        :param str text: new page content
        :param str summary: edit summary
        :param kwargs: Additional query parameters, see `API:Edit`_.

        .. _`API:Edit`: https://www.mediawiki.org/wiki/API:Edit
        """
        if not summary:
            raise Exception("edit summary is mandatory")
        if len(summary) > 255:
            # TODO: the limit is planned to be increased since MW 1.25
            raise Exception("the edit summary is too long, maximum is 255 chars (got len('{}') == {})".format(summary, len(summary)))

        # send text as utf-8 encoded
        text = text.encode("utf-8")

        # md5 hash is used to prevent data corruption during transfer
        h = hashlib.md5()
        h.update(text)
        md5 = h.hexdigest()

        # if bot= is passed, also pass an assertion
        if "bot" in kwargs:
            kwargs["assert"] = "bot"
        else:
            # require being logged in, either as regular user or bot
            kwargs["assert"] = "user"

        # check and apply tags
        if "applychangetags" in self.user.rights and "wiki-scripts" in self.tags.applicable:
            kwargs.setdefault("tags", [])
            kwargs["tags"].append("wiki-scripts")
        elif "applychangetags" not in self.user.rights and "tags" in kwargs:
            logger.warning("Your account does not have the 'applychangetags' right, removing tags from the parameter list: {}".format(kwargs["tags"]))
            del kwargs["tags"]

        logger.info("Creating page [[{}]] ...".format(title))

        try:
            return self.call_with_csrftoken(action="edit", title=title, md5=md5, text=text, summary=summary, createonly="1", **kwargs)
        except APIError as e:
            logger.error("Failed to create page [[{}]] due to APIError (code '{}': {})".format(title, e.server_response["code"], e.server_response["info"]))
            raise

class LoginFailed(Exception):
    """
    Raised when the :py:meth:`API.login` call failed.
    """
    pass
