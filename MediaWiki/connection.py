#! /usr/bin/env python3

# FIXME: query string should be normalized, see https://www.mediawiki.org/wiki/API:Main_page#API_etiquette

import requests
import http.cookiejar as cookielib

from .exceptions import *

DEFAULT_UA = "wiki-scripts/0.1 +https://github.com/lahwaacz/wiki-scripts"

__all__ = ["Connection"]

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
        if http_user is not None and http_password is not None:
            self._auth = (http_user, http_password)

        self.session.headers.update({"user-agent": user_agent})
        self.session.auth = _auth
        self.session.params.update({"format": "json"})
        self.session.verify = ssl_verify

    def call(self, params, method="GET"):
        """
        Basic HTTP request handler.

        :param params: dictionary of query string parameters

        """
        r = self.session.request(method=method, url=self._api_url, params=params)

        # raise HTTPError for bad requests (4XX client errors and 5XX server errors)
        r.raise_for_status()

        if isinstance(self.session.cookies, cookielib.FileCookieJar):
            self.session.cookies.save()

        try:
            return r.json()
        except ValueError as e:
            raise APIJsonError("Failed to decode server response. Please make sure " +
                               "that the API is enabled on the wiki and that the " +
                               "API URL is correct.")
