from ws.utils import *


def test_list_chunks() -> None:
    l = list(range(10))
    chunks = list(list_chunks(l, bs=3))
    expected = [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]
    assert chunks == expected


def test_iter_chunks() -> None:
    l = range(10)
    chunks = iter_chunks(l, bs=3)
    expected = [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]
    for i, j in zip(chunks, expected):
        assert list(i) == j
