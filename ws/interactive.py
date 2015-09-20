#! /usr/bin/env python3

"""
Collection of functions extending :py:class:`ws.core.api.API` with various
interactive tasks.
"""

import os
import shlex
import getpass
import subprocess
import logging

from .diff import diff_highlighted

logger = logging.getLogger(__name__)

__all__ = ["require_login", "edit_interactive", "InteractiveQuit", "ask_yesno"]

_diffprog = shlex.split(os.environ.get("DIFFPROG", "vimdiff"))

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

def edit_interactive(api, title, pageid, text_old, text_new, basetimestamp, summary, **kwargs):
    """
    A routine for interactive editing. Presents differences between the two
    revisions highlighted using :py:func:`ws.diff.diff_highlighted` and an
    interactive prompt to let the user decide what to do next:

    - ``y`` accepts the edit and calls :py:meth:`API.edit <ws.core.api.API.edit>`.
    - ``n`` discards the edit.
    - ``q`` will raise :py:exc:`InteractiveQuit` exception to let the calling
      program know that it should quit.
    - ``e`` will open the revisions in an external merge program (configurable
      by the ``$DIFFPROG`` environment variable, defaults to ``vimdiff``).
    - ``?`` will print brief legend and repeat the highlighted diff and prompt.

    :param api: a :py:class:`MediaWiki.api.API` instance to operate on
    :param str text_old: old page content
    :param str text_new: new page content

    Other parameters are the same as for :py:meth:`ws.core.api.API.edit`.
    """
    options = [
        ("y", "make this edit"),
        ("n", "do not make this edit"),
        ("q", "quit; do not make this edit or any of the following"),
        ("e", "manually edit this edit"),
        ("?", "print this legend"),
    ]
    short_options = [opt[0] for opt in options]
    ans = ""

    while True:
        diff = diff_highlighted(text_old, text_new, title + ".old", title + ".new", basetimestamp, "<utcnow>")
        print(diff)
        print("Edit summary:  " + summary)
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
                args = [_diffprog, wrapper.fname_new, wrapper.fname_old]
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
