#!/usr/bin/env python3

from collections import OrderedDict

from .namespaces import *
from .interwiki import *

from .lists.recentchanges import *
from .lists.logevents import *
from .lists.allpages import *
from .lists.protectedtitles import *
from .lists.allrevisions import *
from .lists.alldeletedrevisions import *

from .props.info import *
from .props.pageprops import *
from .props.revisions import *
from .props.deletedrevisions import *
from .props.templates import *
from .props.transcludedin import *
from .props.links import *
from .props.linkshere import *
from .props.images import *
from .props.categories import *
from .props.langlinks import *

__classes_lists = {
    "recentchanges": RecentChanges,
    "logevents": LogEvents,
    "allpages": AllPages,
    "protectedtitles": ProtectedTitles,
    "allrevisions": AllRevisions,
    "alldeletedrevisions": AllDeletedRevisions,
}

# TODO: generator=allpages works, check the others
__classes_generators = {
    "recentchanges": RecentChanges,
    "allpages": AllPages,
    "protectedtitles": ProtectedTitles,
    "allrevisions": AllRevisions,
    "alldeletedrevisions": AllDeletedRevisions,
}

# MediaWiki's prop=revisions supports 3 modes:
#   1. multiple pages, but only the latest revision
#   2. single page, but all revisions
#   3. specifying revids
# Fuck it, let's have separate "latestrevisions" for mode 1...
__classes_props = {
    "info": Info,
    "pageprops": PageProps,
    "latestrevisions": Revisions,
    "revisions": Revisions,
    "deletedrevisions": DeletedRevisions,
    "templates": Templates,
    "transcludedin": TranscludedIn,
    "links": Links,
    "linkshere": LinksHere,
    "images": Images,
    "categories": Categories,
    "langlinks": LanguageLinks,
}

def list(db, params):
    assert "list" in params
    list = params.pop("list")
    if list not in __classes_lists:
        raise NotImplementedError("Module list={} is not implemented yet.".format(list))
    s = __classes_lists[list](db)
    # TODO: make sure that all parameters are used (i.e. when all modules take their parameters, params_copy should be empty)
    list_params = s.filter_params(params)
    s.set_defaults(list_params)
    s.sanitize_params(list_params)
    query = s.get_select(list_params)

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

    # TODO: for the lack of better structure, we abuse the AllPages class for execution of titles= and pageids= queries
    s = AllPages(db)

    assert "titles" in params or "pageids" in params or "generator" in params
    if "titles" in params:
        titles = params_copy.pop("titles")
        if isinstance(titles, str):
            titles = {titles}
        assert isinstance(titles, set)
        titles = [db.Title(t) for t in titles]
        tail, pageset, ex = get_pageset(db, titles=titles)
    elif "pageids" in params:
        pageids = params_copy.pop("pageids")
        if isinstance(pageids, int):
            pageids = {pageids}
        assert isinstance(pageids, set)
        tail, pageset, ex = get_pageset(db, pageids=pageids)
    elif "generator" in params:
        generator = params_copy.pop("generator")
        if generator not in __classes_generators:
            raise NotImplementedError("Module generator={} is not implemented yet.".format(generator))
        s = __classes_generators[generator](db)
        # TODO: make sure that all parameters are used (i.e. when all modules take their parameters, params_copy should be empty)
        generator_params = s.filter_params(params_copy, generator=True)
        s.set_defaults(generator_params)
        s.sanitize_params(generator_params)
        pageset, tail = s.get_pageset(generator_params)

    # report missing pages (does not make sense for generators)
    if "generator" not in params:
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

    # fetch the pageset into an intermediate list
    # TODO: query-continuation is probably needed for better efficiency
    query = pageset.select_from(tail)
    pages = OrderedDict()  # for indexed access, like in MediaWiki
    result = s.execute_sql(query)
    for row in result:
        entry = s.db_to_api(row)
        pages[entry["pageid"]] = entry
    result.close()

    if "prop" in params:
        prop = params_copy.pop("prop")
        if isinstance(prop, str):
            prop = {prop}
        assert isinstance(prop, set)

        for p in prop:
            if p not in __classes_props:
                raise NotImplementedError("Module prop={} is not implemented yet.".format(p))
            _s = __classes_props[p](db)

            if p == "latestrevisions":
                prop_tail = _s.join_with_pageset(tail, enum_rev_mode=False)
            else:
                prop_tail = _s.join_with_pageset(tail)
            prop_params = _s.filter_params(params_copy)
            _s.set_defaults(prop_params)
            prop_select, prop_tail = _s.get_select_prop(pageset, prop_tail, prop_params)

            query = prop_select.select_from(prop_tail)
            result = _s.execute_sql(query)
            for row in result:
                page = pages[row["page_id"]]
                _s.db_to_api_subentry(page, row)
            result.close()

    yield from pages.values()

def query(db, params=None, **kwargs):
    if params is None:
        params = kwargs
    elif not isinstance(params, dict):
        raise ValueError("params must be dict or None")
    elif kwargs and params:
        raise ValueError("specifying 'params' and 'kwargs' at the same time is not supported")

    if "list" in params:
        return list(db, params)
    elif "titles" in params or "pageids" in params or "generator" in params:
        return query_pageset(db, params)
    raise NotImplementedError("Unknown query: no recognizable parameter ({}).".format(params))
