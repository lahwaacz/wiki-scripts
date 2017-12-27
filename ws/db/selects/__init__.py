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

def query_pageset(db, params):
    s = AllPages(db)
    params_copy = params.copy()

    assert "titles" in params or "pageids" in params
    if "titles" in params:
        titles = params_copy.pop("titles")
        titles = [db.Title(t) for t in titles]
        pageset, ex = s.get_pageset(titles=titles)
    elif "pageids" in params:
        pageids = params_copy.pop("pageids")
        pageset, ex = s.get_pageset(pageids=pageids)

    extra_selects = []
    if "prop" in params:
        prop = params_copy.pop("prop")
        if isinstance(prop, str):
            prop = {prop}
        assert isinstance(prop, set)

        classes_props = {
            "revisions": AllRevisions,
            "deletedrevisions": AllDeletedRevisions,
        }

        for p in prop:
            if p not in classes_props:
                raise NotImplementedError("Module prop={} is not implemented yet.".format(p))
            _s = classes_props[p](db)
            pageset = _s.add_props(pageset, params_copy)
            extra_selects.append(_s)

    # report missing pages
    existing_pages = set()
    # TODO: use some common executor
    result = db.engine.execute(pageset)
    for row in result:
        if "titles" in params:
            existing_pages.add((row.page_namespace, row.page_title))
        elif "pageids" in params:
            existing_pages.add(row.page_id)
    if "titles" in params:
        for t in titles:
            if (t.namespacenumber, t.dbtitle()) not in existing_pages:
                yield {"missing": "", "ns": t.namespacenumber, "title": t.dbtitle()}
    elif "pageids" in params:
        for p in pageids:
            if p not in existing_pages:
                yield {"missing": "", "pageid": p}

    # TODO: use some common executor
    result = db.engine.execute(pageset)
    for row in result:
        api_entry = s.db_to_api(row)
        for _s in extra_selects:
            api_entry = _s.db_to_api(row)
        yield api_entry
    result.close()

def query(db, params=None, **kwargs):
    if params is None:
        params = kwargs
    elif not isinstance(params, dict):
        raise ValueError("params must be dict or None")
    elif kwargs and params:
        raise ValueError("specifying 'params' and 'kwargs' at the same time is not supported")

    if "list" in params:
        return list(db, params)
    elif "titles" in params or "pageids" in params:
        return query_pageset(db, params)
    raise NotImplementedError("Unknown query: no recognizable parameter ({}).".format(params))
