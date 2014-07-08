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

class QueryError(BaseMediaWikiException):
    """ Raised when API:Query fails (response contains "error" attribute)
    """
    pass

class QueryWarnings(BaseMediaWikiException):
    """ Raised when response from API:Query contains warnings
    """
    pass
