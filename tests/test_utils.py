#! /usr/bin/env python3

from nose.tools import assert_equals, assert_true, assert_false

from ws.utils import *

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

def test_flatten_list():
    l = [["a"], ["b", "c"], [1, 2]]
    assert_equals(flatten_list(l), ["a", "b", "c", 1, 2])

def test_parse_date():
    import datetime
    timestamp = "2014-08-25T14:26:59Z"
    expected = datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
    assert_equals(parse_date(timestamp), expected)
