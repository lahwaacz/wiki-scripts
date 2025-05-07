from ws.utils import *


class test_is_ascii:
    """test for utils.is_ascii() function"""

    def test_with_ascii(self) -> None:
        text = "abcdefghijklmnopqrstuvwxyz"
        assert is_ascii(text) is True

    def test_with_nonascii(self) -> None:
        text = "ěščřžýáíéúů"
        for l in text:
            assert is_ascii(l) is False
        assert is_ascii(text) is False


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
