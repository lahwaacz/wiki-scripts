#! /usr/bin/env python3

def canonicalize(title):
    """
    Return a canonical form of the title, that is with underscores replaced with
    spaces, leading and trailing whitespace stripped and first letter
    capitalized.

    :param title: a `str` or `mwparserfromhell.nodes.wikicode.Wikicode` object
    :returns: a `str` object
    """
    title = str(title).replace("_", " ").strip()
    title = title[0].upper() + title[1:]
    return title

# TODO: remove (included only for backwards compatibility)
from .wikicode import *
