#! /usr/bin/env python3

from nose.tools import assert_equals, assert_true, assert_false, raises

from ws.utils import *

def test_parse_date():
    import datetime
    timestamp = "2014-08-25T14:26:59Z"
    expected = datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
    assert_equals(parse_date(timestamp), expected)

class test_is_ascii:
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
