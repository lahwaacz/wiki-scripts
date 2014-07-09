#! /usr/bin/env python3

""" Exceptions used throughout the MediaWiki module
"""

class BaseMediaWikiException(Exception):
    """ Base exception for all following exceptions
    """
    pass

class APIJsonError(BaseMediaWikiException):
    """ Raised when json-decoding of server response failed
    """
    pass

class APIWrongAction(BaseMediaWikiException):
    """ Raised when a wrong API action is specified
    """
    def __init__(self, action, available):
        self.message = "%s (available actions are: %s)" % (action, available)

    def __str__(self):
        return self.message

class APIError(BaseMediaWikiException):
    """ Raised when API response contains ``error`` attribute
    """
    pass

class APIWarnings(BaseMediaWikiException):
    """ Raised when API response contains ``warnings`` attribute
    """
    pass
