#! /usr/bin/env python3

import hashlib
from functools import lru_cache
import logging

from .connection import Connection, APIError
from .rate import RateLimited
from .lazy import LazyProperty

logger = logging.getLogger(__name__)

__all__ = ["API", "LoginFailed"]

# TODO: rename as "Site"?
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
        del self.is_loggedin
        del self.user_rights

        status = do_login(self, username, password)
        if status is True and self.is_loggedin:
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
    def is_loggedin(self):
        """
        Indicates whether the current session is authenticated (``True``) or
        not (``False``).

        The property is evaluated lazily and cached with the
        :py:class:`@LazyProperty <ws.core.lazy.LazyProperty>` decorator.
        """
        result = self.call_api(action="query", meta="userinfo")
        return "anon" not in result["userinfo"]

    @LazyProperty
    def user_rights(self):
        """
        A list of rights for the current user.

        The property is evaluated lazily and cached with the
        :py:class:`@LazyProperty <ws.core.lazy.LazyProperty>` decorator.
        """
        result = self.call_api(action="query", meta="userinfo", uiprop="rights")
        return result["userinfo"]["rights"]

    @LazyProperty
    def interwikimap(self):
        """
        Interwiki prefixes on the wiki, represented as a dictionary where
        keys are the available prefixes and additional information (as returned
        by the `siteinfo/interwikimap` query, see `API:siteinfo`_).

        The property is evaluated lazily and cached with the
        :py:class:`@LazyProperty <ws.core.lazy.LazyProperty>` decorator.

        .. _`API:siteinfo`: https://www.mediawiki.org/wiki/API:Siteinfo
        """
        result = self.call_api(action="query", meta="siteinfo", siprop="interwikimap")
        interwikis = result["interwikimap"]
        return dict( (d["prefix"], d) for d in interwikis )

    @property
    def interlanguagemap(self):
        """
        Interlanguage prefixes on the wiki, filtered from the general
        :py:attr:`interwikimap <ws.core.API.interwikimap>` property.
        """
        return dict( (prefix, info) for prefix, info in self.interwikimap.items() if "local" in info )

# TODO: namespace aliases are not considered
    @LazyProperty
    def namespaces(self):
        """
        Namespaces present on the wiki as a mapping (dictionary) of namespace
        IDs to their names.

        The property is evaluated lazily and cached with the
        :py:class:`@LazyProperty <ws.core.lazy.LazyProperty>` decorator.
        """
        result = self.call_api(action="query", meta="siteinfo", siprop="namespaces")
        namespaces = result["namespaces"].values()
        return dict( (ns["id"], ns["*"]) for ns in namespaces )


    def query_continue(self, params=None, **kwargs):
        """
        Generator for MediaWiki's `query-continue feature`_.

        :param params:
            same as :py:meth:`ws.core.connection.Connection.call_api`, but
            ``action`` is always set to ``"query"`` and ``"continue"`` to ``""``
        :param kwargs:
            same as :py:meth:`ws.core.connection.Connection.call_api`
        :yields: from ``"query"`` part of the API response

        .. _`query-continue feature`: https://www.mediawiki.org/wiki/API:Query#Continuing_queries
        """
        if params is None:
            params = kwargs
        elif not isinstance(params, dict):
            raise ValueError("params must be dict or None")
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

    @lru_cache(maxsize=8)
    def resolve_redirects(self, *pageids):
        """
        Resolve redirect titles according to the `MediaWiki's API`_. List of
        redirect pages must be obtained other way, for example:

        >>> pageids = []
        >>> for ns in ["0", "4", "12"]:
        >>>     pages = api.generator(generator="allpages", gaplimit="max", gapfilterredir="redirects", gapnamespace=ns)
        >>>     _pageids = [str(page["pageid"]) for page in pages]
        >>>     pageids.extend(_pageids)

        Or just use this method when not sure if given title is a redirect or
        not.

        :param pageids:
            unpacked list of page IDs to resolve (i.e. call this method as
            ``resolve_redirects(*list)`` or ``resolve_redirects(pageid1, pageid2, ...)``)
        :returns:
            ``redirects`` part of the API response concatenated into one list

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
        limit = 500 if "apihighlimits" in self.user_rights else 50

        # resolve by chunks
        redirects = []
        for snippet in _chunks(pageids, limit):
            result = self.call_api(action="query", redirects="", pageids="|".join(snippet))
            redirects.extend(result["redirects"])

        return redirects

    # TODO: solve caching of methods with unhashable parameters somehow
#    @lru_cache(maxsize=8)
    def redirects_map(self, source_namespaces=None, target_namespaces="all"):
        """
        Build a mapping of redirects in given namespaces. Interwiki redirects are
        not included in the mapping.

        :param source_namespaces:
            the namespace ID of the source title must be in this list in order
            to be included in the mapping (default is ``[0]``, the magic word
            ``"all"`` will select all available namespaces)
        :param target_namespaces:
            the namespace ID of the target title must be in this list in order
            to be included in the mapping (default is ``"all"``, which will
            select all available namespaces)
        :returns:
            a dictionary where the keys are source titles and values are the
            redirect targets, including the link fragments (e.g.
            ``"Page title#Section title"``).
        """
        source_namespaces = source_namespaces if source_namespaces is not None else [0]
        if source_namespaces == "all":
            source_namespaces = [ns for ns in self.namespaces if int(ns) >= 0]
        if target_namespaces == "all":
            target_namespaces = [ns for ns in self.namespaces if int(ns) >= 0]

        redirects = {}
        for ns in target_namespaces:
            # FIXME: adding the rdnamespace parameter causes an internal API error,
            # see https://wiki.archlinux.org/index.php/User:Lahwaacz/Notes#API:_resolving_redirects
            # removing it for now, all namespaces are included by default anyway...
#            allpages = self.generator(generator="allpages", gapfilterredir="nonredirects", gapnamespace=ns, gaplimit="max", prop="redirects", rdprop="title|fragment", rdnamespace="|".join(source_namespaces), rdlimit="max")
            allpages = self.generator(generator="allpages", gapfilterredir="nonredirects", gapnamespace=ns, gaplimit="max", prop="redirects", rdprop="title|fragment", rdlimit="max")
            for page in allpages:
                # construct the mapping, the query result is somewhat reversed...
                target_title = page["title"]
                for redirect in page.get("redirects", []):
                    source_title = redirect["title"]
                    target_fragment = redirect.get("fragment")
                    if target_fragment:
                        redirects[source_title] = "{}#{}".format(target_title, target_fragment)
                    else:
                        redirects[source_title] = target_title
        return redirects

    @LazyProperty
    def _csrftoken(self):
        logger.debug("Requesting new csrftoken...")
        return self.call_api(action="query", meta="tokens")["tokens"]["csrftoken"]

    def call_with_csrftoken(self, params=None, **kwargs):
        """
        A wrapper around :py:meth:`ws.core.connection.Connection.call_api` with
        automatic management of the `CSRF token`_.

        :param params: same as :py:meth:`ws.core.connection.Connection.call_api`
        :param kwargs: same as :py:meth:`ws.core.connection.Connection.call_api`
        :returns: same as :py:meth:`ws.core.connection.Connection.call_api`

        .. _`CSRF token`: https://www.mediawiki.org/wiki/API:Tokens
        """
        if params is None:
            params = kwargs
        elif not isinstance(params, dict):
            raise ValueError("params must be dict or None")

        # ensure that the token is passed
        params["token"] = self._csrftoken

        # max tries
        max_retries = 2

        retries = max_retries
        while retries > 0:
            try:
                return self.call_api(params, **kwargs)
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
        return self.call_api(params, **kwargs)

    @RateLimited(1, 3)
    def edit(self, title, pageid, text, basetimestamp, summary, **kwargs):
        """
        Interface to `API:Edit`_. MD5 hash of the new text is computed
        automatically and added to the query. This method is rate-limited with
        the :py:class:`@RateLimited <ws.core.rate.RateLimited>` decorator to
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

        logger.info("Editing page '{}' ...".format(title))

        try:
            return self.call_with_csrftoken(action="edit", md5=md5, basetimestamp=basetimestamp, pageid=pageid, text=text, summary=summary, **kwargs)
        except APIError as e:
            logger.error("Failed to edit page '{}' due to APIError (code '{}': {})".format(title, e.server_response["code"], e.server_response["info"]))
            raise

class LoginFailed(Exception):
    """
    Raised when the :py:meth:`API.login` call failed.
    """
    pass
