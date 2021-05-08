#! /usr/bin/env python3

from functools import lru_cache
import hashlib

import requests

__all__ = ["SmarterEncryptionList"]

class SmarterEncryptionList:
    """
    Reference: https://help.duckduckgo.com/duckduckgo-help-pages/privacy/smarter-encryption/
    """

    endpoint = "https://duckduckgo.com/smarter_encryption.js?pv1={hash_prefix}"

    def __init__(self, *, timeout, max_retries, **kwargs):
        self.timeout = timeout

        self.session = requests.Session()
        self.session.verify = True
        adapter = requests.adapters.HTTPAdapter(max_retries=max_retries)
        self.session.mount("https://duckduckgo.com", adapter)

    @lru_cache(maxsize=1024)
    def __contains__(self, value):
        h = hashlib.sha1(bytes(value, encoding="utf-8"))
        data = self._query_hash_prefix(h.hexdigest()[:4])
        return h.hexdigest() in data

    @lru_cache(maxsize=128)
    def _query_hash_prefix(self, value):
        url = self.endpoint.format(hash_prefix=value)
        response = self.session.get(url, timeout=self.timeout)
        # raise HTTPError for bad requests (4XX client errors and 5XX server errors)
        response.raise_for_status()
        return response.json()
