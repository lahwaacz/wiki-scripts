#! /usr/bin/env python3

import pytest

from ws.client.api import LoginFailed

# TODO: pytest attribute
#@attr(speed="slow")
class test_api:
    """
    Some basic sanity checks, intended mostly for detecting changes in the
    ArchWiki configuration.
    """

    # uncategorized categories on ArchWiki (should be only these all the time)
    uncat_cats = ["Category:Archive", "Category:DeveloperWiki", "Category:Languages", "Category:Maintenance", "Category:Sandbox"]

# TODO: not sure if this is such a good idea...
#    # test LoginFailed exception
#    @raises(LoginFailed)
#    def test_login_failed(self):
#        fixtures.api.login("wiki-scripts testing invalid user", "invalid password")

    def test_max_ids_per_query(self, api):
        assert api.max_ids_per_query == 50

    def test_query_continue_dummy(self, api):
        with pytest.raises(ValueError):
            next(api.query_continue(params=0))

    # testing on uncategorized categories (should contain only 5 items all the time)
    def test_query_continue(self, api):
        q = api.query_continue(action="query", list="querypage", qppage="Uncategorizedcategories", qplimit=1)
        titles = []
        for chunk in q:
            titles += [i["title"] for i in chunk["querypage"]["results"]]
        assert titles == self.uncat_cats

    def test_query_continue_params(self, api):
        data = {
            "list": "querypage",
            "qppage": "Uncategorizedcategories",
            "qplimit": 1,
            }
        q = api.query_continue(data)
        titles = []
        for chunk in q:
            titles += [i["title"] for i in chunk["querypage"]["results"]]
        assert titles == self.uncat_cats

    def test_query_continue_params_kwargs(self, api):
        with pytest.raises(ValueError):
            next(api.query_continue(params={"foo": 0}, bar=1))

    def test_list_pagepropnames(self, api):
        expected = ["displaytitle", "hiddencat", "newsectionlink", "noeditsection", "noindex", "notoc"]
        pagepropnames = [d["propname"] for d in api.list(list="pagepropnames")]
        assert pagepropnames == expected

    def test_list_dummy(self, api):
        with pytest.raises(ValueError):
            next(api.list())

    def test_list(self, api):
        q = api.list(list="querypage", qppage="Uncategorizedcategories", qplimit="max")
        titles = []
        for i in q:
            titles.append(i["title"])
        assert titles == self.uncat_cats

    def test_generator_dummy(self, api):
        with pytest.raises(ValueError):
            next(api.generator())

    def test_generator(self, api):
        q = api.generator(generator="querypage", gqppage="Uncategorizedcategories", gqplimit="max")
        titles = []
        for i in q:
            titles.append(i["title"])
        assert titles == self.uncat_cats
