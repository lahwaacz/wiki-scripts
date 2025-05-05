#! /usr/bin/env python3

import hashlib
import logging
from functools import lru_cache

from ws.utils import HTTPXClient

__all__ = ["SmarterEncryptionList"]

logger = logging.getLogger(__name__)

class SmarterEncryptionList:
    """
    Reference: https://help.duckduckgo.com/duckduckgo-help-pages/privacy/smarter-encryption/
    """

    endpoint = "https://duckduckgo.com/smarter_encryption.js?pv1={hash_prefix}"

    def __init__(self, *, timeout, max_retries, **kwargs):
        self.client = HTTPXClient(timeout=timeout, retries=max_retries)

    @lru_cache(maxsize=1024)
    def __contains__(self, value):
        logger.debug("checking domain {} in the SmarterEncryptionList".format(value))
        h = hashlib.sha1(bytes(value, encoding="utf-8"))
        data = self._query_hash_prefix(h.hexdigest()[:4])
        return h.hexdigest() in data

    @lru_cache(maxsize=128)
    def _query_hash_prefix(self, value):
        url = self.endpoint.format(hash_prefix=value)
        response = self.client.get(url)
        # raise HTTPStatusError for bad requests (4XX client errors and 5XX server errors)
        response.raise_for_status()
        return response.json()
