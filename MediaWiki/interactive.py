#! /usr/bin/env python3

"""
Collection of functions extending :py:class:`MediaWiki.api.API` with various
interactive tasks.
"""

import sys
import getpass
from .diff import diff_highlighted

def require_login(api):
    """
    Check if ``"api"`` session is authenticated, otherwise ask for credentials.

    Calls :py:meth:`sys.exit(1)` if login failed.

    :param api: an :py:class:`MediaWiki.api.API` instance
    """
    if not api.is_loggedin():
        print("You need to log in to use this script. URL is %s" % api.api_url)
        api.login(username=input("Username: "), password=getpass.getpass("Password: "))
        if not api.is_loggedin():
            print("Login failed.", file=sys.stderr)
            sys.exit(1)

def edit_interactive(api, pageid, old_text, new_text, basetimestamp, summary, **kwargs):
    # TODO: docstring
    diff = diff_highlighted(old_text, new_text)
    options = [
        ("y", "make this edit"),
        ("n", "do not make this edit"),
        ("q", "quit; do not make this edit or any of the following"),
# TODO:
#            ("e", "manually edit this edit"),
        ("?", "print help"),
    ]
    short_options = [o[0] for o in options]
    ans = ""

    while True:
        print(diff)
        ans = input("Make this edit? [%s]? " % ",".join(short_options))
        if ans == "?" or ans not in short_options:
            for o in options:
                print("%s - %s" % o)
        else:
            break

    if ans == "y":
        return api.edit(pageid, new_text, basetimestamp, summary, **kwargs)
    elif ans == "q":
        sys.exit(1)
