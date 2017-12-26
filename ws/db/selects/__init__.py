#!/usr/bin/env python3

from .namespaces import *
from .interwiki import *
from .recentchanges import *
from .logevents import *
from .allpages import *
from .protectedtitles import *
from .allrevisions import *
from .alldeletedrevisions import *

def list(db, params):
    classes = {
        "recentchanges": RecentChanges,
        "logevents": LogEvents,
        "allpages": AllPages,
        "protectedtitles": ProtectedTitles,
        "allrevisions": AllRevisions,
        "alldeletedrevisions": AllDeletedRevisions,
    }

    assert "list" in params
    list = params.pop("list")
    s = classes[list](db)
    return s.list(params)

def query(db, params=None, **kwargs):
    if params is None:
        params = kwargs
    elif not isinstance(params, dict):
        raise ValueError("params must be dict or None")
    elif kwargs and params:
        raise ValueError("specifying 'params' and 'kwargs' at the same time is not supported")

    if "list" in params:
        return list(db, params)
    raise NotImplementedError("Unknown query: no recognizable parameter ({}).".format(params))
