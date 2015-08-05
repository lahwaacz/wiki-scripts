#! /usr/bin/env python3

# TODO: save+restore log events https://www.mediawiki.org/wiki/API:Logevents

import requests
import http.cookiejar as cookielib
from datetime import datetime

from .core.connection import DEFAULT_UA

class DumpGenerator:

    def __init__(self, api):
        self.api = api
        self.chunk_size = 1024 * 1024

        # FIXME: better way?
        assert(self.api.index_url is not None)

    def _export(self, pages, timestamp_start, outfile):
        # ref: http://www.mediawiki.org/wiki/Manual:Parameters_to_Special:Export
        data = {
            "title": "Special:Export",
            "pages": "\n".join(pages),
            "offset": timestamp_start,
        }
        response = self.api.call_index(method="POST", data=data, stream=True)

        # handle download stream
        with open(outfile, 'wb') as fd:
            for chunk in response.iter_content(self.chunk_size):
                fd.write(chunk)

    def dump(self, outfile, timestamp_start):
        datetime.strptime(timestamp_start, '%Y-%m-%dT%H:%M:%SZ')
        try:
            datetime.strptime(timestamp_start, '%Y-%m-%dT%H:%M:%SZ')
        except ValueError:
            print("Unable to parse timestamp_start. The format is 'YYYY-MM-DDThh:mm:ssZ'.")
            return False

        print("Fetching list of all pages...")
        pages = []
        namespaces = [ns for ns in self.api.namespaces().keys() if ns >= 0]
        for ns in namespaces:
            pages += list([page["title"] for page in self.api.generator(generator="allpages", gaplimit="max", gapnamespace=ns)])

        print("Calling Special:Export...")
        self._export(pages, timestamp_start, outfile)
        return True
