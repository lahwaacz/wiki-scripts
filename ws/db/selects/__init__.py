#!/usr/bin/env python3

from .namespaces import *
from .interwiki import *

from .lists.recentchanges import *
from .lists.logevents import *
from .lists.allpages import *
from .lists.protectedtitles import *
from .lists.allrevisions import *
from .lists.alldeletedrevisions import *

from .props.revisions import *
from .props.deletedrevisions import *
from .props.pageprops import *

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
    s.set_defaults(params)
    s.sanitize_params(params)

    query = s.get_select(params)

    # TODO: some lists like allrevisions should group the results per page like MediaWiki
    result = s.execute_sql(query)
    for row in result:
        yield s.db_to_api(row)
    result.close()

def get_pageset(db, titles=None, pageids=None):
    """
    :param list titles: list of :py:class:`ws.parser_helpers.title.Title` objects
    :param list pageids: list of :py:obj:`int` objects
    """
    assert titles is not None or pageids is not None
    assert titles is None or pageids is None

    # join to get the namespace prefix
    page = db.page
    nss = db.namespace_starname
    tail = page.outerjoin(nss, page.c.page_namespace == nss.c.nss_id)

    s = sa.select([page.c.page_id, page.c.page_namespace, page.c.page_title, nss.c.nss_name])

    if titles is not None:
        ns_title_pairs = [(t.namespacenumber, t.dbtitle()) for t in titles]
        s = s.where(sa.tuple_(page.c.page_namespace, page.c.page_title).in_(ns_title_pairs))
        s = s.order_by(page.c.page_namespace.asc(), page.c.page_title.asc())

        ex = sa.select([page.c.page_namespace, page.c.page_title])
        ex = ex.where(sa.tuple_(page.c.page_namespace, page.c.page_title).in_(ns_title_pairs))
    elif pageids is not None:
        s = s.where(page.c.page_id.in_(pageids))
        s = s.order_by(page.c.page_id.asc())

        ex = sa.select([page.c.page_id])
        ex = ex.where(page.c.page_id.in_(pageids))

    return tail, s, ex

def query_pageset(db, params):
    params_copy = params.copy()

    assert "titles" in params or "pageids" in params
    if "titles" in params:
        titles = params_copy.pop("titles")
        assert isinstance(titles, set)
        titles = [db.Title(t) for t in titles]
        tail, pageset, ex = get_pageset(db, titles=titles)
    elif "pageids" in params:
        pageids = params_copy.pop("pageids")
        tail, pageset, ex = get_pageset(db, pageids=pageids)

    extra_selects = []
    if "prop" in params:
        prop = params_copy.pop("prop")
        if isinstance(prop, str):
            prop = {prop}
        assert isinstance(prop, set)

        # MediaWiki's prop=revisions supports only 3 modes:
        #   1. multiple pages, but only the latest revision
        #   2. single page, but all revisions
        #   3. specifying revids
        # Fuck it, let's have separate "latestrevisions" for mode 1...
        classes_props = {
            "latestrevisions": Revisions,
            "revisions": Revisions,
            "deletedrevisions": DeletedRevisions,
            "pageprops": PageProps,
        }

        for p in prop:
            if p not in classes_props:
                raise NotImplementedError("Module prop={} is not implemented yet.".format(p))
            _s = classes_props[p](db)

            # pass <prefix>prop arguments to the add_props method
            default_prop_params = {}
            _s.set_defaults(default_prop_params)
            prop_params = params_copy.get(_s.API_PREFIX + "prop", default_prop_params["prop"])

            if p == "latestrevisions":
                tail = _s.join_with_pageset(tail, enum_rev_mode=False)
            else:
                tail = _s.join_with_pageset(tail)
            pageset, tail = _s.add_props(pageset, tail, prop_params)
            extra_selects.append(_s)

    # complete the SQL query
    query = pageset.select_from(tail)

    # TODO: for the lack of better structure, we abuse the AllPages class for execution
    s = AllPages(db)

    # report missing pages
    existing_pages = set()
    result = s.execute_sql(ex)
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

    result = s.execute_sql(query)
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
