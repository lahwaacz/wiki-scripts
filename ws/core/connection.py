#! /usr/bin/env python3

# FIXME: query string should be normalized, see https://www.mediawiki.org/wiki/API:Main_page#API_etiquette
#        + 'token' parameter should be specified last, see https://www.mediawiki.org/wiki/API:Edit

# TODO: logging of every query parameters (and response?) as debug level

import requests
import http.cookiejar as cookielib
import logging

from ws import __version__, __url__
from .rate import RateLimited

logger = logging.getLogger(__name__)

__all__ = ["DEFAULT_UA", "Connection", "APIWrongAction", "ConnectionError", "APIJsonError", "APIError"]

DEFAULT_UA = "wiki-scripts/{version} ({url})".format(version=__version__, url=__url__)

API_ACTIONS = [
    "login", "logout", "createaccount", "query", "expandtemplates", "parse",
    "opensearch", "feedcontributions", "feedwatchlist", "help", "paraminfo", "rsd",
    "compare", "tokens", "purge", "setnotificationtimestamp", "rollback", "delete",
    "undelete", "protect", "block", "unblock", "move", "edit", "upload", "filerevert",
    "emailuser", "watch", "patrol", "import", "userrights", "options", "imagerotate"
]
POST_ACTIONS = [
    "login", "createaccount", "purge", "setnotificationtimestamp", "rollback",
    "delete", "undelete", "protect", "block", "unblock", "move", "edit", "upload",
    "filerevert", "emailuser", "watch", "patrol", "import", "userrights", "options",
    "imagerotate"
]

class Connection:
    """
    The base object handling connection between a wiki and scripts.

    It is possible to save the session data by specifying either ``cookiejar``
    or ``cookie_file`` arguments. This way cookies can be saved permanently to
    the disk or shared between multiple :py:class:`Connection` objects.
    If ``cookiejar`` is present ``cookie_file`` is ignored.

    :param api_url: URL path to the wiki's ``api.php`` entry point
    :param index_url: URL path to the wiki's ``index.php`` entry point
    :param user_agent: string sent as ``User-Agent`` header to the web server
    :param ssl_verify: if ``True``, the SSL certificate will be verified
    :param cookie_file: path to a :py:class:`cookielib.FileCookieJar` file
    :param cookiejar: an existing :py:class:`cookielib.CookieJar` object
    """

    # TODO: when #3 is implemented, make index_url mandatory
    def __init__(self, api_url, index_url=None, user_agent=DEFAULT_UA,
                 ssl_verify=None, cookie_file=None, cookiejar=None,
                 http_user=None, http_password=None):
        self.api_url = api_url
        self.index_url = index_url

        self.session = requests.Session()

        if cookiejar is not None:
            self.session.cookies = cookiejar
        elif cookie_file is not None:
            self.session.cookies = cookielib.LWPCookieJar(cookie_file)
            try:
                self.session.cookies.load()
            except cookielib.LoadError:
                self.session.cookies.save()
                self.session.cookies.load()

        _auth = None
        # TODO: replace with requests.auth.HTTPBasicAuth
        if http_user is not None and http_password is not None:
            self._auth = (http_user, http_password)

        self.session.headers.update({"user-agent": user_agent})
        self.session.auth = _auth
        self.session.params.update({"format": "json"})
        self.session.verify = ssl_verify

    @RateLimited(10, 3)
    def request(self, method, url, **kwargs):
        """
        Simple HTTP request handler. It is basically a wrapper around
        :py:func:`requests.request()` using the established session including
        cookies, so it should be used only for connections with ``url`` leading
        to the same site.

        The parameters are the same as for :py:func:`requests.request()`, see
        `Requests documentation`_ for details.

        .. _`Requests documentation`: http://docs.python-requests.org/en/latest/api/
        """
        response = self.session.request(method, url, **kwargs)

        # raise HTTPError for bad requests (4XX client errors and 5XX server errors)
        response.raise_for_status()

        if isinstance(self.session.cookies, cookielib.FileCookieJar):
            self.session.cookies.save()

        return response

    def call_api(self, params=None, expand_result=True, **kwargs):
        """
        Convenient method to call the ``api.php`` entry point.

        Checks the ``action`` parameter (default is ``"help"`` as in the API),
        selects correct HTTP request method, handles API errors and warnings.

        Parameters of the call can be passed either as a dict to ``params``, or
        as keyword arguments.

        :param params: dictionary of API parameters
        :param expand_result:
            if ``True``, return only part of the response relevant to the given
            action, otherwise full response is returned
        :param kwargs: API parameters passed as keyword arguments
        :returns: a dictionary containing (part of) the API response
        """
        if params is None:
            params = kwargs
        elif not isinstance(params, dict):
            raise ValueError("params must be dict or None")

        # check if action is valid
        action = params.setdefault("action", "help")
        if action not in API_ACTIONS:
            raise APIWrongAction(action, API_ACTIONS)

        # select HTTP method and call the API
        if action in POST_ACTIONS:
            # passing `params` to `data` will cause form-encoding to take place,
            # which is necessary when editing pages longer than 8000 characters
            result = self.request("POST", self.api_url, data=params)
        else:
            result = self.request("GET", self.api_url, params=params)

        try:
            result = result.json()
        except ValueError:
            raise APIJsonError("Failed to decode server response. Please make sure " +
                               "that the API is enabled on the wiki and that the " +
                               "API URL is correct.")

        # see if there are errors/warnings
        if "error" in result:
            # for some reason action=help is returned inside 'error'
            if action == "help":
                return result["error"]["*"]
            raise APIError(params, result["error"])
        if "warnings" in result:
            msg = "API warning(s) for query {}:".format(params)
            for warning in result["warnings"].values():
                msg += "\n* {}".format(warning["*"])
            logger.warning(msg)

        if expand_result is True:
            return result[action]
        return result

    def call_index(self, method="GET", **kwargs):
        """
        Convenient method to call the ``index.php`` entry point.

        Currently it only calls :py:meth:`self.request()` with specific URL and
        sets default method to ``"GET"``.

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
    """ Raised when a wrong API action is specified
    """
    def __init__(self, action, available):
        self.message = "%s (available actions are: %s)" % (action, available)

    def __str__(self):
        return self.message

class ConnectionError(Exception):
    """ Base connection exception
    """
    pass

class APIJsonError(ConnectionError):
    """ Raised when json-decoding of server response failed
    """
    pass

class APIError(ConnectionError):
    """ Raised when API response contains ``error`` attribute
    """
    def __init__(self, params, server_response):
        self.message = "\nquery parameters: {}\nserver response: {}".format(params, server_response)
    def __str__(self):
        return self.message
