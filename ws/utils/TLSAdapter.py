#! /usr/bin/env python3

import ssl
import requests
from requests.packages.urllib3.poolmanager import PoolManager
from requests.packages.urllib3.util import ssl_

__all__ = ["TLSAdapter"]

class TLSAdapter(requests.adapters.HTTPAdapter):
    """
    Snippet based on https://stackoverflow.com/a/44432829

    Example:

        session = requests.session()
        # disallow TLS1.0 and TLS1.1, allow only TLS1.2 (and newer if suported
        # by the used openssl version)
        adapter = TLSAdapter(ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1)
        session.mount("https://", adapter)
    """

    def __init__(self, *, ssl_options=0, **kwargs):
        self.ssl_options = ssl_options
        super(TLSAdapter, self).__init__(**kwargs)

    def init_poolmanager(self, *pool_args, **pool_kwargs):
        ctx = ssl_.create_urllib3_context(ssl.PROTOCOL_TLS)
        # extend the default context options, which is to disable SSL2, SSL3
        # and SSL compression, see:
        # https://github.com/shazow/urllib3/blob/6a6cfe9/urllib3/util/ssl_.py#L241
        ctx.options |= self.ssl_options
        self.poolmanager = PoolManager(*pool_args, ssl_context=ctx, **pool_kwargs)
