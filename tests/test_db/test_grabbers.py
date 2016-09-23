#! /usr/bin/env python3

from copy import copy

from ws.grabbers import namespace

# TODO: monkeypatch api.site.namespaces to avoid API queries

def test_namespace(api, db):
    ns = copy(api.site.namespaces)
    del ns[-1]
    del ns[-2]

    g = namespace.GrabberNamespaces(api, db)
    g.update()
    assert namespace.select(db) == ns

    # void update for coverage
    g = namespace.GrabberNamespaces(api, db)
    g.update()
    assert namespace.select(db) == ns
