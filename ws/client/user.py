#! /usr/bin/env python3

import datetime

from .meta import Meta
from ..utils import LazyProperty

class User(Meta):
    """
    The :py:class:`User` class holds and interacts with information about the
    current user.

    Valid properties are listed in the :py:attr:`properties` attribute.
    See the `MediaWiki documentation`_ for explanation of the properties.

    All :py:attr:`properties` are evaluated lazily and cached. All cached
    properties are automatically invalidated after :py:attr:`timeout` seconds,
    except :py:attr:`volatile_properties`, which are invalidated after
    :py:attr:`volatile_timeout` seconds.

    .. _`MediaWiki documentation`: https://www.mediawiki.org/wiki/API:Userinfo
    """

    module = "userinfo"
    properties = {"name", "id", "blockinfo", "hasmsg", "groups", "implicitgroups",
            "rights", "changeablegroups", "options", "editcount", "ratelimits",
            "email", "realname", "acceptlang", "registrationdate", "unreadcount"}
    volatile_properties = {"hasmsg", "editcount", "unreadcount"}
    timeout = 3600
    volatile_timeout = 300

    def __init__(self, api):
        super().__init__(api)

    @LazyProperty
    def is_loggedin(self):
        """
        Indicates whether the current session is authenticated (``True``) or
        not (``False``).

        The property is evaluated lazily and cached with the
        :py:class:`@LazyProperty <ws.utils.lazy.LazyProperty>` decorator.
        """
        return "anon" not in self.fetch()

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
