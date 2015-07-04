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

class TemplateParametersError(BaseMediaWikiException):
    """ Raised when parsing a template parameter failed.
    """
    def __init__(self, template):
        self.message = "Failed to parse a template parameter. This likely indicates a " \
                       "syntax error on the page.\n\n" \
                       "Template text: '{}'\n\n" \
                       "Parsed parameters: {}".format(template, template.params)

    def __str__(self):
        return self.message
