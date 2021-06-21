#! /usr/bin/env python3

import logging
from functools import lru_cache
import hashlib

import requests
import ssl
from ws.utils import TLSAdapter

__all__ = ["SmarterEncryptionList"]

logger = logging.getLogger(__name__)

class SmarterEncryptionList:
    """
    Reference: https://help.duckduckgo.com/duckduckgo-help-pages/privacy/smarter-encryption/
    """

    endpoint = "https://duckduckgo.com/smarter_encryption.js?pv1={hash_prefix}"

    def __init__(self, *, timeout, max_retries, **kwargs):
        self.timeout = timeout

        self.session = requests.Session()
        # disallow TLS1.0 and TLS1.1, allow only TLS1.2 (and newer if suported
        # by the used openssl version)
        ssl_options = ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
        adapter = TLSAdapter(ssl_options=ssl_options, max_retries=max_retries)
        self.session.mount("https://", adapter)

    @lru_cache(maxsize=1024)
    def __contains__(self, value):
        logger.debug("checking domain {} in the SmarterEncryptionList".format(value))
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
