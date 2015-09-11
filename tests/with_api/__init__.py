#! /usr/bin/env python3

from ws.core.api import API

class fixtures:
    api = None

def setup_package():
    # NOTE: anonymous, will be very slow for big data!
    api_url = "https://wiki.archlinux.org/api.php"
    index_url = "https://wiki.archlinux.org/index.php"
    ssl_verify = True
    fixtures.api = API(api_url, index_url, ssl_verify=ssl_verify)

def teardown_package():
    fixtures.api = None
