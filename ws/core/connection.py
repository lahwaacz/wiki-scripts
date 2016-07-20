#! /usr/bin/env python3

"""
The :py:mod:`ws.core.connection` module provides a low-level interface for
connections to the wiki. The :py:class:`requests.Session` class from the
:py:mod:`requests` library is used to manage the cookies, authentication
and making requests.
"""

# FIXME: query string should be normalized, see https://www.mediawiki.org/wiki/API:Main_page#API_etiquette
#        + 'token' parameter should be specified last, see https://www.mediawiki.org/wiki/API:Edit

import requests
import http.cookiejar as cookielib
import logging

from ws import __version__, __url__
from ..utils import RateLimited

logger = logging.getLogger(__name__)

__all__ = ["DEFAULT_UA", "Connection", "APIWrongAction", "APIJsonError", "APIError"]

DEFAULT_UA = "wiki-scripts/{version} ({url})".format(version=__version__, url=__url__)

API_ACTIONS = {
     "abusefiltercheckmatch", "abusefilterchecksyntax", "abusefilterevalexpression",
     "abusefilterunblockautopromote", "block", "checktoken", "clearhasmsg", "compare",
     "createaccount", "delete", "edit", "emailuser", "expandtemplates", "feedcontributions",
     "feedrecentchanges", "feedwatchlist", "filerevert", "help", "imagerotate", "import",
     "login", "logout", "managetags", "move", "opensearch", "options", "paraminfo", "parse",
     "patrol", "protect", "purge", "query", "revisiondelete", "rollback", "rsd",
     "setnotificationtimestamp", "stashedit", "tag", "tokens", "unblock", "undelete",
     "upload", "userrights", "watch"
}
POST_ACTIONS = {
    "login", "createaccount", "purge", "setnotificationtimestamp", "rollback",
    "delete", "undelete", "protect", "block", "unblock", "move", "edit", "upload",
    "filerevert", "emailuser", "watch", "patrol", "import", "userrights", "options",
    "imagerotate", "revisiondelete", "abusefilterunblockautopromote", "managetags", "tag",
    "stashedit"
}

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
    :param max_retries:
        Maximum number of retries for each connection. Applies only to
        failed DNS lookups, socket connections and connection timeouts, never
        to requests where data has made it to the server.
    :param timeout: connection timeout in seconds
    :param cookie_file: path to a :py:class:`cookielib.FileCookieJar` file
    :param cookiejar: an existing :py:class:`cookielib.CookieJar` object
    """

    def __init__(self, api_url, index_url, user_agent=DEFAULT_UA,
                 ssl_verify=None, max_retries=0, timeout=30,
                 cookie_file=None, cookiejar=None,
                 http_user=None, http_password=None):
        self.api_url = api_url
        self.index_url = index_url
        self.timeout = timeout

        self.session = requests.Session()

        if cookiejar is not None:
            self.session.cookies = cookiejar
        elif cookie_file is not None:
            self.session.cookies = cookielib.LWPCookieJar(cookie_file)
            try:
                self.session.cookies.load()
            except (cookielib.LoadError, FileNotFoundError):
                self.session.cookies.save()
                self.session.cookies.load()

        self._auth = None
        if http_user is not None and http_password is not None:
            self._auth = (http_user, http_password)

        self.session.headers.update({"user-agent": user_agent})
        self.session.auth = self._auth
        self.session.params.update({"format": "json"})
        self.session.verify = ssl_verify

        adapter = requests.adapters.HTTPAdapter(max_retries=max_retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

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
        group.add_argument("--api-url", metavar="URL",
                help="the URL to the wiki's api.php (default: %(default)s)")
        group.add_argument("--index-url", metavar="URL",
                help="the URL to the wiki's api.php (default: %(default)s)")
        group.add_argument("--ssl-verify", default=True, type=ws.config.argtype_bool,
                help="whether to verify SSL certificates (default: %(default)s)")
        group.add_argument("--connection-max-retries", default=3, type=int,
                help="maximum number of retries for each connection (default: %(default)s)")
        group.add_argument("--connection-timeout", default=30, type=float,
                help="connection timeout in seconds (default: %(default)s)")
        group.add_argument("--cookie-file", type=ws.config.argtype_dirname_must_exist, metavar="PATH",
                help="path to cookie file (default: $cache_dir/$site.cookie)")
        # TODO: expose also user_agent, http_user, http_password?

    @classmethod
    def from_argparser(klass, args):
        """
        Construct a :py:class:`Connection` object from arguments parsed by
        :py:class:`argparse.ArgumentParser`.

        :param args:
            an instance of :py:class:`argparse.Namespace`. In addition to the
            arguments set by :py:meth:`Connection.set_argparser`,
            it is expected to also contain ``site`` and ``cache_dir`` arguments.
        :returns: an instance of :py:class:`Connection`
        """
        if args.cookie_file is None:
            import os
            if not os.path.exists(args.cache_dir):
                os.mkdir(args.cache_dir)
            cookie_file = args.cache_dir + "/" + args.site + ".cookie"
        else:
            cookie_file = args.cookie_file
        # retype from int to bool
        args.ssl_verify = True if args.ssl_verify == 1 else False
        return klass(args.api_url, args.index_url, ssl_verify=args.ssl_verify,
                     max_retries=args.connection_max_retries, timeout=args.connection_timeout,
                     cookie_file=cookie_file)

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

    def call_api(self, params=None, expand_result=True, **kwargs):
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
            raise APIError(params, result["error"])
        if "warnings" in result:
            msg = "API warning(s) for query {}:".format(params)
            for warning in result["warnings"].values():
                msg += "\n* {}".format(warning["*"])
            logger.warning(msg)

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
