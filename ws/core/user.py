#! /usr/bin/env python3

import datetime

from .lazy import LazyProperty

class User:
    """
    The :py:class:`User` class holds and interacts with information about the
    current user.

    Valid properties are listed in the :py:attr:`properties` attribute.
    See the `MediaWiki documentation`_ for explanation of the properties.

    All :py:attr:`properties` are evaluated lazily and cached with the
    :py:class:`@LazyProperty <ws.core.lazy.LazyProperty>` decorator.
    All cached properties are automatically invalidated after
    :py:attr:`timeout` seconds, except :py:attr:`volatile_properties`, which
    are invalidated after :py:attr:`volatile_timeout` seconds.

    .. _`MediaWiki documentation`: https://www.mediawiki.org/wiki/API:Userinfo
    """

    properties = {"blockinfo", "hasmsg", "groups", "implicitgroups", "rights",
            "changeablegroups", "options", "editcount", "ratelimits", "email",
            "realname", "acceptlang", "registrationdate", "unreadcount"}
    volatile_properties = {"hasmsg", "editcount", "unreadcount"}
    timeout = 3600
    volatile_timeout = 300

    def __init__(self, api):
        self._api = api
        self._values = {}
        self._timestamps = {}

    def _get(self, uiprop=None):
        """
        Auxiliary method for querying a single property.
        """
        if uiprop is None:
            result = self._api.call_api(action="query", meta="userinfo")
            return result["userinfo"]
        elif isinstance(uiprop, list):
            result = self._api.call_api(action="query", meta="userinfo", uiprop="|".join(uiprop))
            return result["userinfo"]
        else:
            result = self._api.call_api(action="query", meta="userinfo", uiprop=uiprop)
            return result["userinfo"][uiprop]

    def __getattr__(self, attr):
        if attr not in self.properties:
            raise AttributeError("Invalid attribute: '{}'. Valid attributes are: {}".format(attr, self.properties))

        utcnow = datetime.datetime.utcnow()
        if attr in self.volatile_properties:
            threshold = utcnow - datetime.timedelta(seconds=self.volatile_timeout)
        else:
            threshold = utcnow - datetime.timedelta(seconds=self.timeout)

        if attr not in self._values or self._timestamps[attr] < threshold:
            self._values[attr] = self._get(attr)
            self._timestamps[attr] = utcnow
        return self._values[attr]

    @LazyProperty
    def is_loggedin(self):
        """
        Indicates whether the current session is authenticated (``True``) or
        not (``False``).

        The property is evaluated lazily and cached with the
        :py:class:`@LazyProperty <ws.core.lazy.LazyProperty>` decorator.
        """
        return "anon" not in self._get()

    def set_option(self, option, value):
        """
        Change preferences of the current user.

        See the list of `available options`_ on MediaWiki.

        .. _`available options`: https://www.mediawiki.org/wiki/API:Options#Available_Options

        :param str option: the option to be changed
        :param str value:
            the value to be set (if empty, it will be reset to the default value)
        """
        if value:
            return self._api.call_with_csrftoken(action="options", optionname=option, optionvalue=value)
        return self._api.call_with_csrftoken(action="options", change=option)
