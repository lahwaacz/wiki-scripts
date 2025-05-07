import datetime

from ws.utils import *


def test_parse_date() -> None:
    timestamp = "2014-08-25T14:26:59Z"
    expected = datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
    assert parse_date(timestamp) == expected


def test_format_date() -> None:
    timestamp = datetime.datetime(2014, 8, 25, 14, 26, 59)
    expected = "2014-08-25T14:26:59Z"
    assert format_date(timestamp) == expected


def test_range_by_days() -> None:
    first = datetime.datetime(2000, 1, 30, 8, 35, 42)
    last = datetime.datetime(2000, 2, 2, 13, 25, 53)
    ran = range_by_days(first, last)
    expected = [
        datetime.date(2000, 1, 30),
        datetime.date(2000, 1, 31),
        datetime.date(2000, 2, 1),
        datetime.date(2000, 2, 2),
    ]
    assert ran == expected


def test_range_by_months() -> None:
    first = datetime.datetime(2000, 10, 30, 8, 35, 42)
    last = datetime.datetime(2001, 2, 2, 13, 25, 53)
    ran = range_by_months(first, last)
    expected = [
        datetime.date(2000, 10, 1),
        datetime.date(2000, 11, 1),
        datetime.date(2000, 12, 1),
        datetime.date(2001, 1, 1),
        datetime.date(2001, 2, 1),
        datetime.date(2001, 3, 1),
    ]
    assert ran == expected


def test_round_to_seconds() -> None:
    dts = [
        (
            datetime.datetime(2000, 1, 1, 1, 2, 3, 0),
            datetime.datetime(2000, 1, 1, 1, 2, 3),
        ),
        (
            datetime.datetime(2000, 1, 1, 1, 2, 3, 100000),
            datetime.datetime(2000, 1, 1, 1, 2, 3),
        ),
        (
            datetime.datetime(2000, 1, 1, 1, 2, 3, 200000),
            datetime.datetime(2000, 1, 1, 1, 2, 3),
        ),
        (
            datetime.datetime(2000, 1, 1, 1, 2, 3, 300000),
            datetime.datetime(2000, 1, 1, 1, 2, 3),
        ),
        (
            datetime.datetime(2000, 1, 1, 1, 2, 3, 400000),
            datetime.datetime(2000, 1, 1, 1, 2, 3),
        ),
        (
            datetime.datetime(2000, 1, 1, 1, 2, 3, 500000),
            datetime.datetime(2000, 1, 1, 1, 2, 4),
        ),
        (
            datetime.datetime(2000, 1, 1, 1, 2, 3, 600000),
            datetime.datetime(2000, 1, 1, 1, 2, 4),
        ),
        (
            datetime.datetime(2000, 1, 1, 1, 2, 3, 700000),
            datetime.datetime(2000, 1, 1, 1, 2, 4),
        ),
        (
            datetime.datetime(2000, 1, 1, 1, 2, 3, 800000),
            datetime.datetime(2000, 1, 1, 1, 2, 4),
        ),
        (
            datetime.datetime(2000, 1, 1, 1, 2, 3, 900000),
            datetime.datetime(2000, 1, 1, 1, 2, 4),
        ),
    ]
    for orig, rounded in dts:
        assert round_to_seconds(orig) == rounded
