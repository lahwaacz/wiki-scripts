#! /usr/bin/env python3

import ssl
import requests
from requests.packages.urllib3.poolmanager import PoolManager

__all__ = ["TLSAdapter"]

class TLSAdapter(requests.adapters.HTTPAdapter):
    """ Adapter which disallows TLS1.0 and TLS1.1, allows only TLS1.2
        (and newer if supported by the used openssl version).
    """
    def init_poolmanager(self, *pool_args, **pool_kwargs):
        # TODO: urllib3 2.0.0 added ssl_minimum_version and deprecated ssl_version, see https://urllib3.readthedocs.io/en/stable/changelog.html
        # TLS v1.2 is actually used by default in urllib3 2.0.0: https://urllib3.readthedocs.io/en/stable/advanced-usage.html#tls-minimum-and-maximum-versions
        self.poolmanager = PoolManager(*pool_args, ssl_version=ssl.PROTOCOL_TLSv1_2, **pool_kwargs)
