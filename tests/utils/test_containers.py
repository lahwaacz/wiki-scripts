#! /usr/bin/env python3

import pytest

from ws.utils import *

def test_wrapper():
    l = [
        {"name": "Betty", "id": 0},
        {"name": "Anne", "id": 2},
        {"name": "Cecilia", "id": 1},
    ]
    wrapped_names = ListOfDictsAttrWrapper(l, "name")
    wrapped_ids = ListOfDictsAttrWrapper(l, "id")
    assert list(wrapped_names) == ["Betty", "Anne", "Cecilia"]
    assert list(wrapped_ids) == [0, 2, 1]

class test_bisect_find:
    def test_id(self):
        l = [
            {"name": "Betty", "id": 0},
            {"name": "Anne", "id": 1},
            {"name": "Cecilia", "id": 2},
        ]
        wrapped_ids = ListOfDictsAttrWrapper(l, "id")
        d = bisect_find(l, 1, index_list=wrapped_ids)
        assert d == {"name": "Anne", "id": 1}
        assert d == l[1]

    def test_name(self):
        l = [
            {"name": "Anne", "id": 0},
            {"name": "Betty", "id": 2},
            {"name": "Cecilia", "id": 1},
        ]
        wrapped_names = ListOfDictsAttrWrapper(l, "name")
        d = bisect_find(l, "Betty", index_list=wrapped_names)
        assert d == {"name": "Betty", "id": 2}
        assert d == l[1]

    def test_fail_unordered_id(self):
        l = [
            {"name": "Anne", "id": 0},
            {"name": "Betty", "id": 2},
            {"name": "Cecilia", "id": 1},
            {"name": "Daisy", "id": 3},
        ]
        wrapped_ids = ListOfDictsAttrWrapper(l, "id")
        with pytest.raises(IndexError):
            d = bisect_find(l, 2, index_list=wrapped_ids)

class test_bisect_insert_or_replace:
    def test_insert(self):
        expected = [
            {"name": "Anne", "id": 1},
            {"name": "Betty", "id": 0},
            {"name": "Cecilia", "id": 2},
            {"name": "Daisy", "id": 3},
        ]
        l = []
        wrapped_names = ListOfDictsAttrWrapper(l, "name")
        bisect_insert_or_replace(l, "Cecilia", {"name": "Cecilia", "id": 2}, wrapped_names)
        bisect_insert_or_replace(l, "Daisy", {"name": "Daisy", "id": 3}, wrapped_names)
        bisect_insert_or_replace(l, "Betty", {"name": "Betty", "id": 0}, wrapped_names)
        bisect_insert_or_replace(l, "Anne", {"name": "Anne", "id": 1}, wrapped_names)
        assert l == expected

    def test_replace(self):
        l = [
            {"name": "Anne", "id": 0},
            {"name": "Betty", "id": 1},
            {"name": "Cecilia", "id": 2},
            {"name": "Daisy", "id": 3},
        ]
        expected = [
            {"name": "Anne", "id": 1},
            {"name": "Betty", "id": 0},
            {"name": "Cecilia", "id": 3},
            {"name": "Daisy", "id": 2},
        ]
        wrapped_names = ListOfDictsAttrWrapper(l, "name")
        bisect_insert_or_replace(l, "Anne", {"name": "Anne", "id": 1}, wrapped_names)
        bisect_insert_or_replace(l, "Betty", {"name": "Betty", "id": 0}, wrapped_names)
        bisect_insert_or_replace(l, "Cecilia", {"name": "Cecilia", "id": 3}, wrapped_names)
        bisect_insert_or_replace(l, "Daisy", {"name": "Daisy", "id": 2}, wrapped_names)
        assert l == expected

class test_dmerge:
    def test_type(self):
        with pytest.raises(TypeError):
            dmerge({"foo": "bar"}, "baz")

    def test_shallow(self):
        src = {"foo": 0, "bar": 1}
        dest = {"foo": 1, "baz": 2}
        dmerge(src, dest)
        assert dest == {"foo": 0, "bar": 1, "baz": 2}

    def test_nested_dict(self):
        src = {"bar": {"foo": 2}}
        dest = {
            "foo": 0,
            "bar": {"baz": 1},
        }
        dmerge(src, dest)
        assert dest == {"foo": 0, "bar": {"foo": 2, "baz": 1}}

    def test_nested_list(self):
        src = {"foo": [1, 2]}
        dest = {"foo": [0, 1]}
        dmerge(src, dest)
        assert dest == {"foo": [0, 1, 1, 2]}

class test_find_caseless:
    src = ["Foo", "bar"]

    @pytest.mark.parametrize("what, where, from_target, expected",
            [("foo", src, False, "foo"),
             ("Bar", src, False, "Bar"),
             ("foo", src, True, "Foo"),
             ("Bar", src, True, "bar"),
            ])
    def test_list(self, what, where, from_target, expected):
        result = find_caseless(what, where, from_target)
        assert result == expected

    @pytest.mark.parametrize("what, where, from_target",
            [("foo", [], False),
             ("foo", [], True),
             ("foo", ["bar"], False),
             ("foo", ["bar"], True),
            ])
    def test_notfound(self, what, where, from_target):
        with pytest.raises(ValueError):
            find_caseless(what, where, from_target)

class test_gen_nested_values:
    def test_1(self):
        struct = {
            "a": "b",
            "c": {
                "d": "e",
                "f": [
                    "g",
                    {
                        "h": "i",
                        "j": "k",
                    },
                ],
            }
        }
        result = list(gen_nested_values(struct))
        expected = [
            (["a"], "b"),
            (["c", "d"], "e"),
            (["c", "f", 0], "g"),
            (["c", "f", 1, "h"], "i"),
            (["c", "f", 1, "j"], "k"),
        ]
        assert result == expected

    def test_2(self):
        struct = [
            "a",
            {
                "c": {
                    "d": "e",
                    "f": [
                        "g",
                        {
                            "h": "i",
                            "j": "k",
                        },
                    ],
                }
            }
        ]
        result = list(gen_nested_values(struct))
        expected = [
            ([0], "a"),
            ([1, "c", "d"], "e"),
            ([1, "c", "f", 0], "g"),
            ([1, "c", "f", 1, "h"], "i"),
            ([1, "c", "f", 1, "j"], "k"),
        ]
        assert result == expected
