#! /usr/bin/env python3

"""
Collection of functions extending :py:class:`MediaWiki.api.API` with various
interactive tasks.
"""

import os
import sys
import getpass
import subprocess

from .diff import diff_highlighted

__all__ = ["require_login", "edit_interactive", "InteractiveQuit"]

def require_login(api):
    """
    Check if ``"api"`` session is authenticated, otherwise ask for credentials.

    :param api: an :py:class:`MediaWiki.api.API` instance
    """
    if not api.is_loggedin():
        print("You need to log in to use this script. URL is %s" % api.api_url)
        api.login(username=input("Username: "), password=getpass.getpass("Password: "))

class TmpFileSeries:
    """
    Resource management wrapper around a series of temporary files. Use it with the
    `with` statement.

    Reference: http://stackoverflow.com/questions/865115/how-do-i-correctly-clean-up-a-python-object/865272#865272
    """
    def __init__(self, basename, text_new, text_old, suffix="mediawiki", dir="/tmp"):
        self.fname_new = "{}/{}.new.{}".format(dir, basename, suffix)
        self.file_new = open(self.fname_new, "w+")
        self.file_new.write(text_new)
        self.file_new.flush()

        self.fname_old = "{}/{}.old.{}".format(dir, basename, suffix)
        self.file_old = open(self.fname_old, "w+")
        self.file_old.write(text_old)
        self.file_old.flush()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        os.unlink(self.fname_new)
        os.unlink(self.fname_old)

class InteractiveQuit(Exception):
    """
    Raised when the user specified `quit` on the interactive prompt.
    """
    pass

# TODO: needs 'title' argument (to be shown in diff and for aptly named tmpfiles)
# TODO: vimdiff should be configurable (depends on #3)
def edit_interactive(api, pageid, text_old, text_new, basetimestamp, summary, **kwargs):
    # TODO: docstring
    options = [
        ("y", "make this edit"),
        ("n", "do not make this edit"),
        ("q", "quit; do not make this edit or any of the following"),
        ("e", "manually edit this edit"),
        ("?", "print help"),
    ]
    short_options = [opt[0] for opt in options]
    ans = ""

    while True:
        diff = diff_highlighted(text_old, text_new)
        print(diff)
        ans = input("Make this edit? [%s]? " % ",".join(short_options))

        if ans == "?" or ans not in short_options:
            for opt in options:
                print("%s - %s" % opt)
        elif ans == "y":
            return api.edit(pageid, text_new, basetimestamp, summary, **kwargs)
        elif ans == "n":
            break
        elif ans == "q":
            raise InteractiveQuit
        elif ans == "e":
            with TmpFileSeries(pageid, text_new, text_old) as wrapper:
                cmd = "vimdiff {} {}".format(wrapper.fname_new, wrapper.fname_old)
                try:
                    subprocess.check_call(cmd, shell=True)
                    wrapper.file_new.seek(0)
                    text_new = wrapper.file_new.read()
                    print("Command '{}' exited succesfully.".format(cmd))
                except subprocess.CalledProcessError as e:
                    print("Failed command: '{}' (return code {})".format(cmd, e.returncode), file=sys.stderr)
