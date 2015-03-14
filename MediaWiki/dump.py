#! /usr/bin/env python3

# TODO: save+restore log events https://www.mediawiki.org/wiki/API:Logevents

import requests
import http.cookiejar as cookielib
from datetime import datetime

from .connection import DEFAULT_UA

class DumpGenerator:

    def __init__(self, api, index_url, cookie_file=None, cookiejar=None,
                 user_agent=DEFAULT_UA, http_user=None, http_password=None,
                 ssl_verify=None):
        self.api = api
        self.index_url = index_url
        self.chunk_size = 1024 * 1024

        # Special:Export is not part of the API for some reason, see
        # http://www.mediawiki.org/wiki/Manual:Parameters_to_Special:Export
        # TODO: the rest of this method is duplicated from Connection.__init__,
        #       see if it can be reused in the future
        self.session = requests.Session()

        if cookiejar is not None:
            self.session.cookies = cookiejar
        elif cookie_file is not None:
            self.session.cookies = cookielib.LWPCookieJar(cookie_file)
            try:
                self.session.cookies.load()
            except (cookielib.LoadError, OSError):
                self.session.cookies.save()
                self.session.cookies.load()

        _auth = None
        # TODO: replace with requests.auth.HTTPBasicAuth
        if http_user is not None and http_password is not None:
            self._auth = (http_user, http_password)

        self.session.headers.update({"user-agent": user_agent})
        self.session.auth = _auth
#        self.session.params.update({"format": "json"})
        self.session.verify = ssl_verify

    def _export(self, pages, timestamp_start, outfile):
        # ref: http://www.mediawiki.org/wiki/Manual:Parameters_to_Special:Export
        data = {
            "title": "Special:Export",
            "pages": "\n".join(pages),
            "offset": timestamp_start,
        }

        # this is almost the same as Connection._call() but with stream=True
        response = self.session.request(method="POST", url=self.index_url, data=data, stream=True)

        # raise HTTPError for bad requests (4XX client errors and 5XX server errors)
        response.raise_for_status()

        # handle download stream
        with open(outfile, 'wb') as fd:
            for chunk in response.iter_content(self.chunk_size):
                fd.write(chunk)

        if isinstance(self.session.cookies, cookielib.FileCookieJar):
            self.session.cookies.save()

    def _get_namespaces_ids(self):
        meta = self.api.call(action="query", meta="siteinfo", siprop="namespaces")
        namespaces = meta["namespaces"].values()
        return [ns["id"] for ns in namespaces if ns["id"] >= 0]

    def dump(self, outfile, timestamp_start):
        datetime.strptime(timestamp_start, '%Y-%m-%dT%H:%M:%SZ')
        try:
            datetime.strptime(timestamp_start, '%Y-%m-%dT%H:%M:%SZ')
        except ValueError:
            print("Unable to parse timestamp_start. The format is 'YYYY-MM-DDThh:mm:ssZ'.")
            return False

        print("Fetching list of all pages...")
        pages = []
        for ns in self._get_namespaces_ids():
            pages += list([page["title"] for page in self.api.generator(generator="allpages", gaplimit="max", gapnamespace=ns)])

        print("Calling Special:Export...")
        self._export(pages, timestamp_start, outfile)
        return True
