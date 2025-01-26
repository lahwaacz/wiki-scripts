#! /usr/bin/env python3

import hashlib
import logging

from ..utils import LazyProperty, RateLimited
from .connection import APIError, Connection
from .redirects import Redirects
from .site import Site
from .tags import Tags
from .user import User

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
        # reset the properties related to login
        del self.user
        del self.max_ids_per_query
        del self._csrftoken

        # get token and log in
        token = self.call_api(action="query", meta="tokens", type="login")["tokens"]["logintoken"]
        result = self.call_api(action="login", lgname=username, lgpassword=password, lgtoken=token)
        status = result["result"] == "Success"

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

        See also :py:meth:`API.call_api_autoiter_ids`.
        """
        return 500 if "apihighlimits" in self.user.rights else 50

    @property
    def last_revision_id(self):
        """
        ID of the last revision on the wiki.

        This property is not cached since it may change very often.

        .. note::
            The total edit count is available in `global statistics`_, but it is
            different from the last revision ID obtained from recentchanges.

        .. _`global statistics`: https://wiki.archlinux.org/api.php?action=query&meta=siteinfo&siprop=statistics
        """
        params = {
            "action": "query",
            "list": "recentchanges",
            "rcprop": "ids",
            "rctype": "edit|new",
            "rclimit": "1",
        }
        recentchanges = self.call_api(params)["recentchanges"]
        if len(recentchanges) == 0:
            return None
        return recentchanges[0]["revid"]

    @property
    def oldest_rc_timestamp(self):
        """
        A timestamp of the oldest entry stored in the ``recentchanges`` table.

        Items in the recentchanges table are periodically purged according to
        the `$wgRCMaxAge`_ setting. The value is very important for algorithms
        using ``list=recentchanges`` with specific timespan.

        This property is not cached since it may change (though not very often).

        .. _`$wgRCMaxAge`: http://www.mediawiki.org/wiki/Manual:$wgRCMaxAge
        """
        params = {
            "action": "query",
            "list": "recentchanges",
            "rcprop": "timestamp",
            "rcdir": "newer",
            "rclimit": "1",
        }
        recentchanges = self.call_api(params)["recentchanges"]
        if len(recentchanges) == 0:
            return None
        return recentchanges[0]["timestamp"]

    @property
    def newest_rc_timestamp(self):
        """
        Returns a timestamp of the newest entry stored in the ``recentchanges`` table.
        """
        params = {
            "action": "query",
            "list": "recentchanges",
            "rcprop": "timestamp",
            "rcdir": "older",
            "rclimit": "1",
        }
        recentchanges = self.call_api(params)["recentchanges"]
        if len(recentchanges) == 0:
            return None
        return recentchanges[0]["timestamp"]

    def Title(self, title):
        """
        Parse a MediaWiki title.

        :param str title: page title to be parsed
        :returns: a :py:class:`ws.parser_helpers.title.Title` object
        """
        # lazy import - ws.parser_helpers.title imports mwparserfromhell which is
        # an optional dependency
        from ..parser_helpers.title import Context, Title
        return Title(Context.from_api(self), title)


    def call_api_autoiter_ids(self, params=None, *, expand_result=True, **kwargs):
        """
        A wrapper method around :py:meth:`Connection.call_api` which
        automatically splits the call into multiple queries due to
        :py:attr:`API.max_ids_per_query`.

        Note that this is applicable only to the ``titles``, ``pageids`` and
        ``revids`` API parameters which have to be supplied as :py:class:`!list`
        or :py:class:`set` to this method. Exactly one of these parameters has
        to be supplied.

        The parameters have the same meaning as those in the
        :py:meth:`Connection.call_api` method.

        This method is a generator which yields the results of the call to the
        :py:meth:`Connection.call_api` method for each chunk.
        """
        if params is None:
            params = kwargs
        elif not isinstance(params, dict):
            raise ValueError("params must be dict or None")
        elif kwargs and params:
            # To let kwargs override params, we would have to create deep copy
            # of params to avoid modifying the caller's data and then call
            # utils.dmerge. Too complicated, not supported.
            raise ValueError("specifying 'params' and 'kwargs' at the same time is not supported")

        if "titles" in params:
            iter_key = "titles"
        elif "pageids" in params:
            iter_key = "pageids"
        elif "revids" in params:
            iter_key = "revids"
        else:
            raise ValueError("neither of the parameters titles, pageids or revids is present")

        iter_values = params[iter_key]
        if not isinstance(iter_values, list) and not isinstance(iter_values, set):
            raise TypeError("the value of the parameter '{}' must be either a list or a set".format(iter_key))
        # code below expects a list
        iter_values = sorted(iter_values)

        chunk_size = self.max_ids_per_query
        while iter_values:
            logger.debug("call_api_autoiter_ids: current chunk size is {}".format(chunk_size))
            # take the next chunk
            chunk = iter_values[:chunk_size]
            # update params
            params[iter_key] = "|".join(str(v) for v in chunk)
            # call
            chunk_result = self.call_api(params, expand_result=False, check_warnings=False)
            # check for truncation warning
            if "warnings" in chunk_result:
                msg = "API warning(s) for query {}:".format(params)
                truncated = False
                for warning in chunk_result["warnings"].values():
                    if "This result was truncated" in warning["*"] and chunk_size > 1:
                        truncated = True
                    msg += "\n* {}".format(warning["*"])
                if truncated is True:
                    # truncated result - decrease chunk size and try again
                    chunk_size //= 2
                    continue
                logger.warning(msg)
            elif chunk_size < self.max_ids_per_query // 10:
                # try to grow the chunk size if it dropped too much
                chunk_size *= 4
            # yield the chunk result
            if expand_result is True:
                action = params.get("action")
                if action in chunk_result:
                    yield chunk_result[action]
                else:
                    raise APIExpandResultFailed
            yield chunk_result
            # remove the processed values
            iter_values = iter_values[chunk_size:]

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
        :py:meth:`query_continue`, the overlapping data is not squashed
        automatically in order to avoid keeping big data in memory (this is the
        point of API:Generators). As a result, a page may be yielded multiple
        times. For applications where this matters, see
        :py:meth:`ws.interlanguage.InterlanguageLinks.InterlanguageLinks._get_allpages`
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

        # max tries
        max_retries = 2

        retries = max_retries
        while retries > 0:
            try:
                # ensure that the new token is passed when renewed
                params["token"] = self._csrftoken
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

        # require being logged in, either as regular user or bot
        kwargs.setdefault("assert", "user")

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
            ecode = e.server_response["code"]
            einfo = e.server_response["info"]
            logger.error(f"Failed to edit page [[{title}]] due to APIError (code '{ecode}': {einfo})")
            raise

    @RateLimited(1, 3)
    def create(self, title, text, summary, **kwargs):
        """
        Specialization of :py:meth:`edit` for creating pages. The ``createonly``
        parameter is always added to the query. This method is rate-limited with
        the :py:class:`@RateLimited <ws.utils.rate.RateLimited>` decorator to
        allow 1 call per 3 seconds.

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
            ecode = e.server_response["code"]
            einfo = e.server_response["info"]
            logger.error(f"Failed to create page [[{title}]] due to APIError (code '{ecode}': {einfo})")
            raise

    @RateLimited(1, 3)
    def move(self, from_title, to_title, reason, *, movetalk=True, movesubpages=True, noredirect=False, **kwargs):
        """
        Interface to `API:Move`_. This method is rate-limited with the
        :py:class:`@RateLimited <ws.utils.rate.RateLimited>` decorator to allow
        1 call per 3 seconds.

        :param str from_title: the original title of the page to be renamed
        :param str to_title: the new title of the page to be renamed
        :param str reason: reason for the rename
        :param bool movetalk: rename the associated talk page, if it exists
        :param bool subpages: rename subpages, if applicable
        :param bool noredirect: don't create a redirect
        :param kwargs: Additional query parameters, see `API:Move`_.

        .. _`API:Move`: https://www.mediawiki.org/wiki/API:Move
        """
        kwargs["action"] = "move"
        kwargs["from"] = from_title
        kwargs["to"] = to_title
        kwargs["reason"] = reason
        if movetalk is True:
            kwargs["movetalk"] = "true"
        if movesubpages is True:
            kwargs["movesubpages"] = "true"
        if noredirect is True:
            kwargs["noredirect"] = "true"

        # check and apply tags
        if "applychangetags" in self.user.rights and "wiki-scripts" in self.tags.applicable:
            kwargs.setdefault("tags", [])
            kwargs["tags"].append("wiki-scripts")
        elif "applychangetags" not in self.user.rights and "tags" in kwargs:
            logger.warning("Your account does not have the 'applychangetags' right, removing tags from the parameter list: {}".format(kwargs["tags"]))
            del kwargs["tags"]

        logger.info("Moving page [[{}]] to [[{}]] ...".format(from_title, to_title))

        try:
            return self.call_with_csrftoken(**kwargs)
        except APIError as e:
            ecode = e.server_response["code"]
            einfo = e.server_response["info"]
            logger.error(f"Failed to move page [[{from_title}]] to [[{to_title}]] due to APIError (code '{ecode}': {einfo})")
            raise

    @RateLimited(1, 3)
    def set_page_language(self, title, lang, reason, **kwargs):
        """
        Interface to `API:SetPageLanguage`_. This method is rate-limited with the
        :py:class:`@RateLimited <ws.utils.rate.RateLimited>` decorator to allow
        1 call per 3 seconds.

        :param str title: title of the page whose language should be changed
        :param str lang: language code of the language to be set for the page
        :param str reason: reason for the change
        :param kwargs: Additional query parameters, see `API:SetPageLanguage`_.

        .. _`API:SetPageLanguage`: https://www.mediawiki.org/wiki/API:SetPageLanguage
        """
        kwargs["action"] = "setpagelanguage"
        kwargs["title"] = title
        kwargs["lang"] = lang
        kwargs["reason"] = reason

        # check and apply tags
        if "applychangetags" in self.user.rights and "wiki-scripts" in self.tags.applicable:
            kwargs.setdefault("tags", [])
            kwargs["tags"].append("wiki-scripts")
        elif "applychangetags" not in self.user.rights and "tags" in kwargs:
            logger.warning("Your account does not have the 'applychangetags' right, removing tags from the parameter list: {}".format(kwargs["tags"]))
            del kwargs["tags"]

        logger.info(f"Setting the page language of [[{title}]] to {lang} ...")

        try:
            return self.call_with_csrftoken(**kwargs)
        except APIError as e:
            ecode = e.server_response["code"]
            einfo = e.server_response["info"]
            logger.error(f"Failed to set page language of [[{title}]] to {lang} due to APIError (code '{ecode}': {einfo})")
            raise

class LoginFailed(Exception):
    """
    Raised when the :py:meth:`API.login` call failed.
    """
    pass

class APIExpandResultFailed(APIError):
    """
    Raised when the :py:meth:`API.call_api_autoiter_ids` fails to expand an API
    response while iterating over the split ID set.
    """
    pass

class ShortRecentChangesError(Exception):
    """
    Should be raised by clients to indicate that changes from the requested
    timespan are not available in the ``recentchanges`` table.
    """
    pass
