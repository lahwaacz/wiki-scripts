#! /usr/bin/env python3

from nose.tools import assert_equals, assert_true, assert_false

import datetime

from ws.utils import *

def test_parse_date():
    timestamp = "2014-08-25T14:26:59Z"
    expected = datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
    assert_equals(parse_date(timestamp), expected)

def test_range_by_days():
    first = datetime.datetime(2000, 1, 30,  8, 35, 42)
    last = datetime.datetime(2000, 2, 2,  13, 25, 53)
    ran = range_by_days(first, last)
    expected = [
        datetime.date(2000, 1, 30),
        datetime.date(2000, 1, 31),
        datetime.date(2000, 2, 1),
        datetime.date(2000, 2, 2),
    ]
    assert_equals(ran, expected)

def test_range_by_months():
    first = datetime.datetime(2000, 10, 30,  8, 35, 42)
    last = datetime.datetime(2001, 2, 2,  13, 25, 53)
    ran = range_by_months(first, last)
    expected = [
        datetime.date(2000, 10, 1),
        datetime.date(2000, 11, 1),
        datetime.date(2000, 12, 1),
        datetime.date(2001, 1, 1),
        datetime.date(2001, 2, 1),
        datetime.date(2001, 3, 1),
    ]
    assert_equals(ran, expected)
