#! /usr/bin/env python3

"""
Collection of functions extending :py:class:`ws.core.api.API` with various
interactive tasks.
"""

import os
import getpass
import subprocess
import logging

from .diff import diff_highlighted

logger = logging.getLogger(__name__)

__all__ = ["require_login", "edit_interactive", "InteractiveQuit", "ask_yesno"]

def require_login(api):
    """
    Check if the current ``api`` session is authenticated, otherwise ask for
    credentials.

    :param api: an :py:class:`ws.core.api.API` instance
    """
    if not api.is_loggedin:
        print("You need to log in to use this script. URL is %s" % api.api_url)
        api.login(username=input("Username: "), password=getpass.getpass("Password: "))

class TmpFileSeries:
    """
    Resource management wrapper around a series of temporary files. Use it with
    the `with` statement.

    Reference: http://stackoverflow.com/questions/865115/how-do-i-correctly-clean-up-a-python-object/865272#865272
    """
    def __init__(self, basename, text_new, text_old, suffix="mediawiki", dir="/tmp"):
        self.fname_new = "{}/{}.new.{}".format(dir, basename, suffix)
        self.file_new = open(self.fname_new, "w+")
        # text_new might be Wikicode object, but file.write() checks the type
        self.file_new.write(str(text_new))
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
    Raised when the user specified ``quit`` on the interactive prompt.
    """
    pass

# TODO: needs 'title' argument (to be shown in diff and for aptly named tmpfiles)
# TODO: vimdiff should be configurable (depends on #3)
def edit_interactive(api, title, pageid, text_old, text_new, basetimestamp, summary, **kwargs):
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
        diff = diff_highlighted(text_old, text_new, title + ".old", title + ".new", basetimestamp, "<utcnow>")
        print(diff)
        ans = input("Make this edit? [%s]? " % ",".join(short_options))

        if ans == "?" or ans not in short_options:
            for opt in options:
                print("%s - %s" % opt)
        elif ans == "y":
            return api.edit(title, pageid, text_new, basetimestamp, summary, **kwargs)
        elif ans == "n":
            break
        elif ans == "q":
            raise InteractiveQuit
        elif ans == "e":
            basename = title.replace(" ", "_").replace("/", "_")
            with TmpFileSeries(basename, text_new, text_old) as wrapper:
                args = ["vimdiff", wrapper.fname_new, wrapper.fname_old]
                try:
                    subprocess.check_call(args)
                    wrapper.file_new.seek(0)
                    text_new = wrapper.file_new.read()
                    logger.info("Command {} exited succesfully.".format(args))
                except subprocess.CalledProcessError:
                    logger.exception("Command {} failed.".format(args))

def ask_yesno(question):
    ans = ""
    while True:
        ans = input(question + " [y/n] ")
        if ans == "y":
            return True
        elif ans == "n":
            return False
