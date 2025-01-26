#! /usr/bin/env python3

"""
The :py:mod:`ws.client.connection` module provides a low-level interface for
connections to the wiki. The :py:class:`requests.Session` class from the
:py:mod:`requests` library is used to manage the cookies, authentication
and making requests.
"""

# FIXME: query string should be normalized, see https://www.mediawiki.org/wiki/API:Main_page#API_etiquette
#        + 'token' parameter should be specified last, see https://www.mediawiki.org/wiki/API:Edit

import copy
import http.cookiejar as cookielib
import logging

import requests
from requests.packages.urllib3.util.retry import Retry

from ws import __url__, __version__
from ws.utils import RateLimited, TLSAdapter, parse_timestamps_in_struct, serialize_timestamps_in_struct

logger = logging.getLogger(__name__)

__all__ = ["DEFAULT_UA", "Connection", "APIWrongAction", "APIJsonError", "APIError"]

DEFAULT_UA = "wiki-scripts/{version} ({url})".format(version=__version__, url=__url__)

GET_ACTIONS = {
    'acquiretempusername',
    'changecontentmodel',
    'checktoken',
    'clearhasmsg',
    'compare',
    'expandtemplates',
    'feedcontributions',
    'feedrecentchanges',
    'feedwatchlist',
    'help',
    'logout',
    'opensearch',
    'paraminfo',
    'parse',
    'query',
    'rsd',
}
POST_ACTIONS = {
    'block',
    'changeauthenticationdata',
    'clientlogin',
    'createaccount',
    'cspreport',
    'delete',
    'edit',
    'emailuser',
    'filerevert',
    'imagerotate',
    'linkaccount',
    'login',
    'managetags',
    'mergehistory',
    'move',
    'options',
    'patrol',
    'protect',
    'purge',
    'removeauthenticationdata',
    'resetpassword',
    'revisiondelete',
    'rollback',
    'setnotificationtimestamp',
    'setpagelanguage',  # MW 1.29
    'stashedit',
    'tag',
    'unblock',
    'undelete',
    'unlinkaccount',
    'userrights',
    'validatepassword',  # MW 1.29
    'watch',
}
MULTIPART_FORM_DATA = {
    'import': {'xml'},
    'upload': {'file', 'chunk'},
}
API_ACTIONS = GET_ACTIONS | POST_ACTIONS | set(MULTIPART_FORM_DATA.keys())

class Connection:
    """
    The base object handling connection between a wiki and scripts.

    :param str api_url: URL path to the wiki's ``api.php`` entry point
    :param str index_url: URL path to the wiki's ``index.php`` entry point
    :param requests.Session session: session created by :py:meth:`make_session`
    :param int timeout: connection timeout in seconds
    """

    def __init__(self, api_url, index_url, session, timeout=60):
        self.api_url = api_url
        self.index_url = index_url
        self.session = session
        self.timeout = timeout

    @staticmethod
    def make_session(user_agent=DEFAULT_UA, max_retries=0,
                     cookie_file=None, cookiejar=None,
                     http_user=None, http_password=None):
        """
        Creates a :py:class:`requests.Session` object for the connection.

        It is possible to save the session data by specifying either ``cookiejar``
        or ``cookie_file`` arguments. If ``cookiejar`` is present, ``cookie_file``
        is ignored.

        :param str user_agent: string sent as ``User-Agent`` header to the web server
        :param int max_retries:
            Maximum number of retries for each connection. Applies only to
            failed DNS lookups, socket connections and connection timeouts, never
            to requests where data has made it to the server.
        :param str cookie_file: path to a :py:class:`cookielib.FileCookieJar` file
        :param cookiejar: an existing :py:class:`cookielib.CookieJar` object
        :returns: :py:class:`requests.Session` object
        """
        session = requests.Session()

        if cookiejar is not None:
            session.cookies = cookiejar
        elif cookie_file is not None:
            session.cookies = cookielib.LWPCookieJar(cookie_file)
            try:
                session.cookies.load()
            except (cookielib.LoadError, FileNotFoundError):
                session.cookies.save()
                session.cookies.load()

        _auth = None
        if http_user is not None and http_password is not None:
            _auth = (http_user, http_password)

        session.headers.update({"user-agent": user_agent})
        session.auth = _auth
        session.params.update({"format": "json"})

        # granular control over requests' retries: https://stackoverflow.com/a/35504626
        retries = Retry(total=max_retries, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        adapter = TLSAdapter(max_retries=retries)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    @staticmethod
    def set_argparser(argparser):
        """
        Add arguments for constructing a :py:class:`Connection` object to an
        instance of :py:class:`argparse.ArgumentParser`.

        See also the :py:mod:`ws.config` module.

        :param argparser: an instance of :py:class:`argparse.ArgumentParser`
        """
        import ws.config
        group = argparser.add_argument_group(title="Connection parameters")
        group.add_argument("--api-url", metavar="URL", required=True,
                help="the URL to the wiki's api.php")
        group.add_argument("--index-url", metavar="URL", required=True,
                help="the URL to the wiki's index.php")
        group.add_argument("--connection-max-retries", default=3, type=int,
                help="maximum number of retries for each connection (default: %(default)s)")
        group.add_argument("--connection-timeout", default=60, type=float,
                help="connection timeout in seconds (default: %(default)s)")
        group.add_argument("--cookie-file", type=ws.config.argtype_dirname_must_exist, metavar="PATH",
                help="path to cookie file (default: %(default)s)")
        # TODO: expose also user_agent, http_user, http_password?

    @classmethod
    def from_argparser(klass, args):
        """
        Construct a :py:class:`Connection` object from arguments parsed by
        :py:class:`argparse.ArgumentParser`.

        :param args: an instance of :py:class:`argparse.Namespace`.
        :returns: an instance of :py:class:`Connection`
        """
        session = Connection.make_session(max_retries=args.connection_max_retries,
                                          cookie_file=args.cookie_file)
        return klass(args.api_url, args.index_url, session=session, timeout=args.connection_timeout)

    @RateLimited(10, 3)
    def request(self, method, url, **kwargs):
        """
        Simple HTTP request handler. It is basically a wrapper around
        :py:func:`requests.request()` using the established session including
        cookies, so it should be used only for connections with ``url`` leading
        to the same site.

        The parameters are the same as for :py:func:`requests.request()`, see
        `Requests documentation`_ for details.

        There is no translation of exceptions, the :py:mod:`requests` exceptions
        (notably :py:exc:`requests.exceptions.ConnectionError`,
        :py:exc:`requests.exceptions.Timeout` and
        :py:exc:`requests.exceptions.HTTPError`) should be catched by the caller.

        .. _`Requests documentation`: http://docs.python-requests.org/en/latest/api/
        """
        response = self.session.request(method, url, timeout=self.timeout, **kwargs)

        # raise HTTPError for bad requests (4XX client errors and 5XX server errors)
        response.raise_for_status()

        if isinstance(self.session.cookies, cookielib.FileCookieJar):
            self.session.cookies.save()

        return response

    def call_api(self, params=None, *, expand_result=True, check_warnings=True, **kwargs):
        """
        Convenient method to call the ``api.php`` entry point.

        Checks the ``action`` parameter (default is ``"help"`` as in the API),
        selects correct HTTP request method, handles API errors and warnings.

        Parameters of the call can be passed either as a dict to ``params``, or
        as keyword arguments. ``params`` and ``kwargs`` cannot be specified at
        the same time.

        :param params: dictionary of API parameters
        :param expand_result:
            if ``True``, return only part of the response relevant to the given
            action, otherwise full response is returned
        :param check_warnings:
            if ``True``, the response is investigated and all API warnings are
            output into the logger
        :param kwargs: API parameters passed as keyword arguments
        :returns: a dictionary containing (part of) the API response
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

        # check if action is valid
        action = params.setdefault("action", "help")
        if action not in API_ACTIONS:
            raise APIWrongAction(action, API_ACTIONS)

        # request response inside JSON structure
        if action == "help":
            params["wrap"] = "1"

        # serialize timestamps
        params = copy.deepcopy(params)
        serialize_timestamps_in_struct(params)

        # select HTTP method and call the API
        if action in MULTIPART_FORM_DATA:
            # parameters specified in MULTIPART_FORM_DATA have to be uploaded as "files"
            files = dict((k, v) for k, v in params.items() if k in MULTIPART_FORM_DATA[action])
            for k in files:
                del params[k]
            result = self.request("POST", self.api_url, data=params, files=files)
        # we also form-encode queries with titles, revids and pageids because the
        # URL might be too long for GET, especially in case of titles
        elif action in POST_ACTIONS or (action == "query" and {"titles", "revids", "pageids"} & set(params.keys())):
            # passing `params` to `data` will cause form-encoding to take place,
            # which is necessary when editing pages longer than 8000 characters
            result = self.request("POST", self.api_url, data=params)
        else:
            result = self.request("GET", self.api_url, params=params)

        try:
            result = result.json()
        except ValueError:
            raise APIJsonError("Failed to decode server response. Please make "
                               "sure that the API is enabled on the wiki and "
                               "that the API URL is correct.")

        # see if there are errors/warnings
        if "error" in result:
            raise APIError(params, result["error"])
        if check_warnings is True and "warnings" in result:
            msg = "API warning(s) for query {}:".format(params)
            for warning in result["warnings"].values():
                msg += "\n* {}".format(warning["*"])
            logger.warning(msg)

        # parse timestamps
        parse_timestamps_in_struct(result)

        if expand_result is True:
            if action in result:
                return result[action]
            else:
                raise APIExpandResultFailed
        return result

    def call_index(self, method="GET", **kwargs):
        """
        Convenient method to call the ``index.php`` entry point.

        Currently it only calls :py:meth:`self.request()` with specific URL, default
        method ``"GET"`` and other ``kwargs`` (at least ``"params"`` or ``"data"``
        should be specified).

        See `MediaWiki`_ for possible parameters to ``index.php``.

        .. _`MediaWiki`: https://www.mediawiki.org/wiki/Manual:Parameters_to_index.php
        """
        return self.request(method, self.index_url, **kwargs)

    def get_hostname(self):
        """
        :returns: the hostname part of `self.api_url`
        """
        return requests.packages.urllib3.util.url.parse_url(self.api_url).hostname

class APIWrongAction(Exception):
    """ Raised when a wrong API action is specified.

    This is a programming error, it should be fixed in the client code.
    """
    def __init__(self, action, available):
        self.message = "%s (available actions are: %s)" % (action, available)

    def __str__(self):
        return self.message

class APIJsonError(Exception):
    """ Raised when json-decoding of server response failed.
    """
    pass

class APIError(Exception):
    """ Raised when API response contains ``error`` attribute.
    """
    def __init__(self, params, server_response):
        self.params = params
        self.server_response = server_response

    def __str__(self):
        return "\nquery parameters: {}\nserver response: {}".format(self.params, self.server_response)

class APIExpandResultFailed(Exception):
    """ Raised when expansion of API query result failed.
    """
    pass
