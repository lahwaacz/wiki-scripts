#! /usr/bin/env python3

# FIXME: query string should be normalized, see https://www.mediawiki.org/wiki/API:Main_page#API_etiquette
#        + 'token' parameter should be specified last, see https://www.mediawiki.org/wiki/API:Edit

import requests
import http.cookiejar as cookielib

from .exceptions import *

DEFAULT_UA = "wiki-scripts/0.2 (+https://github.com/lahwaacz/wiki-scripts)"

__all__ = ["Connection"]

api_actions = [
    "login", "logout", "createaccount", "query", "expandtemplates", "parse",
    "opensearch", "feedcontributions", "feedwatchlist", "help", "paraminfo", "rsd",
    "compare", "tokens", "purge", "setnotificationtimestamp", "rollback", "delete",
    "undelete", "protect", "block", "unblock", "move", "edit", "upload", "filerevert",
    "emailuser", "watch", "patrol", "import", "userrights", "options", "imagerotate"
]
post_actions = [
    "login", "createaccount", "purge", "setnotificationtimestamp", "rollback",
    "delete", "undelete", "protect", "block", "unblock", "move", "edit", "upload",
    "filerevert", "emailuser", "watch", "patrol", "import", "userrights", "options",
    "imagerotate"
]

class Connection:
    """
    The base object handling connection between a wiki and scripts.

    It is possible to save the session data by specifying either *cookiejar*
    or *cookie_file* arguments. This way cookies can be saved permanently to
    the disk or shared between multiple :py:class:`Connection` objects.
    If *cookiejar* is present *cookie_file* is ignored.

    :param api_url: URL path to the wiki API endpoint
    :param cookie_file: path to a :py:class:`cookielib.FileCookieJar` file
    :param cookiejar: an existing :py:class:`cookielib.CookieJar` object
    :param user_agent: string sent as ``User-Agent`` header to the web server
    :param ssl_verify: if ``True``, the SSL certificate will be verified
    """

    def __init__(self, api_url, cookie_file=None, cookiejar=None,
                 user_agent=DEFAULT_UA, http_user=None, http_password=None,
                 ssl_verify=None):
        # TODO: document parameters
        self._api_url = api_url

        self.session = requests.Session()

        if cookiejar is not None:
            self.session.cookies = cookiejar
        elif cookie_file is not None:
            self.session.cookies = cookielib.LWPCookieJar(cookie_file)
            try:
                self.session.cookies.load()
            except:
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

    def _call(self, params=None, data=None, method="GET"):
        """
        Basic HTTP request handler.

        At least one of the parameters ``params`` and ``data`` has to be provided,
        see `Requests documentation`_ for details.

        :param params: dictionary of query string parameters
        :param data: data for the request (if a dictionary is provided, form-encoding will take place)
        :returns: dictionary containing full API response

        .. _`Requests documentation`: http://docs.python-requests.org/en/latest/api/
        """
        r = self.session.request(method=method, url=self._api_url, params=params, data=data)

        # raise HTTPError for bad requests (4XX client errors and 5XX server errors)
        r.raise_for_status()

        if isinstance(self.session.cookies, cookielib.FileCookieJar):
            self.session.cookies.save()

        try:
            return r.json()
        except ValueError:
            raise APIJsonError("Failed to decode server response. Please make sure " +
                               "that the API is enabled on the wiki and that the " +
                               "API URL is correct.")

    def call(self, params=None, expand_result=True, **kwargs):
        """
        Convenient method to call the API.

        Checks the ``action`` parameter (default is ``"help"`` as in the API),
        selects correct HTTP request method, handles API errors and warnings.

        Parameters of the call can be passed either as a dict to ``params``, or as
        keyword arguments.

        :param params: dictionary of API parameters
        :param expand_result: if True, return only part of the response relevant
                        to the given action, otherwise full response is returned
        :param kwargs: API parameters passed as keyword arguments
        :returns: dictionary containing (part of) the API response
        """
        if params is None:
            params = kwargs
        elif not isinstance(params, dict):
            raise ValueError("params must be dict or None")

        # check if action is valid
        action = params.get("action", "help")
        if action not in api_actions:
            raise APIWrongAction(action, api_actions)

        # select HTTP method and call the API
        if action in post_actions:
            # passing `params` to `data` will cause form-encoding to take place,
            # which is necessary when editing pages longer than 8000 characters
            result = self._call(data=params, method="POST")
        else:
            result = self._call(params=params, method="GET")

        # see if there are errors/warnings
        if "error" in result:
            # for some reason action=help is returned inside 'error'
            if action == "help":
                return result["error"]["*"]
            raise APIError(result["error"])
        if "warnings" in result:
            # FIXME: don't raise on warnings
            raise APIWarnings(result["warnings"])

        if expand_result is True:
            return result[action]
        return result
