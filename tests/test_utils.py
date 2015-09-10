#! /usr/bin/env python3

from nose.tools import assert_equals, assert_true, assert_false, raises

from ws.utils import *

def test_parse_date():
    import datetime
    timestamp = "2014-08-25T14:26:59Z"
    expected = datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
    assert_equals(parse_date(timestamp), expected)

class test_is_ascii():
    """ test for utils.is_ascii() function
    """

    def test_with_ascii(self):
        text = "abcdefghijklmnopqrstuvwxyz"
        assert_true(is_ascii(text))

    def test_with_nonascii(self):
        text = "ěščřžýáíéúů"
        for l in text:
            assert_false(is_ascii(l))
        assert_false(is_ascii(text))

def test_list_chunks():
    l = list(range(10))
    chunks = list(list_chunks(l, bs=3))
    expected = [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]
    assert_equals(chunks, expected)

def test_iter_chunks():
    l = range(10)
    chunks = iter_chunks(l, bs=3)
    expected = [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]
    for i, j in zip(chunks, expected):
        assert_equals(list(i), j)

def test_wrapper():
    l = [
        {"name": "Betty", "id": 0},
        {"name": "Anne", "id": 2},
        {"name": "Cecilia", "id": 1},
    ]
    wrapped_names = ListOfDictsAttrWrapper(l, "name")
    wrapped_ids = ListOfDictsAttrWrapper(l, "id")
    assert_equals(list(wrapped_names), ["Betty", "Anne", "Cecilia"])
    assert_equals(list(wrapped_ids), [0, 2, 1])

class test_bisect_find():
    def test_id(self):
        l = [
            {"name": "Betty", "id": 0},
            {"name": "Anne", "id": 1},
            {"name": "Cecilia", "id": 2},
        ]
        wrapped_ids = ListOfDictsAttrWrapper(l, "id")
        d = bisect_find(l, 1, index_list=wrapped_ids)
        assert_equals(d, {"name": "Anne", "id": 1})
        assert_equals(d, l[1])

    def test_name(self):
        l = [
            {"name": "Anne", "id": 0},
            {"name": "Betty", "id": 2},
            {"name": "Cecilia", "id": 1},
        ]
        wrapped_names = ListOfDictsAttrWrapper(l, "name")
        d = bisect_find(l, "Betty", index_list=wrapped_names)
        assert_equals(d, {"name": "Betty", "id": 2})
        assert_equals(d, l[1])

    @raises(IndexError)
    def test_fail_unordered_id(self):
        l = [
            {"name": "Anne", "id": 0},
            {"name": "Betty", "id": 2},
            {"name": "Cecilia", "id": 1},
            {"name": "Daisy", "id": 3},
        ]
        wrapped_ids = ListOfDictsAttrWrapper(l, "id")
        d = bisect_find(l, 2, index_list=wrapped_ids)
        assert_equals(d, {"name": "Betty", "id": 2})
