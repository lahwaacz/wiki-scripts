#! /usr/bin/env python3

from nose.tools import assert_equals, assert_true, assert_false, raises

from ws.utils import *

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

class test_bisect_find:
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
        assert_equals(l, expected)

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
        assert_equals(l, expected)

class test_dmerge:
    @raises(TypeError)
    def test_type(self):
        dmerge({"foo": "bar"}, "baz")

    def test_shallow(self):
        src = {"foo": 0, "bar": 1}
        dest = {"foo": 1, "baz": 2}
        dmerge(src, dest)
        assert_equals(dest, {"foo": 0, "bar": 1, "baz": 2})

    def test_nested_dict(self):
        src = {"bar": {"foo": 2}}
        dest = {
            "foo": 0,
            "bar": {"baz": 1},
        }
        dmerge(src, dest)
        assert_equals(dest, {"foo": 0, "bar": {"foo": 2, "baz": 1}})

    def test_nested_list(self):
        src = {"foo": [1, 2]}
        dest = {"foo": [0, 1]}
        dmerge(src, dest)
        assert_equals(dest, {"foo": [0, 1, 1, 2]})

class test_find_caseless:
    def _do_test_1(self, what, where, from_target=False, expected=None):
        result = find_caseless(what, where, from_target)
        assert_equals(result, expected)

    def test_list(self):
        src = ["Foo", "bar"]
        yield self._do_test_1, "foo", src, False, "foo"
        yield self._do_test_1, "Bar", src, False, "Bar"
        yield self._do_test_1, "foo", src, True, "Foo"
        yield self._do_test_1, "Bar", src, True, "bar"

    @raises(ValueError)
    def _do_test_2(self, what, where, from_target=False):
        find_caseless(what, where, from_target)

    def test_notfound(self):
        yield self._do_test_2, "foo", [], False
        yield self._do_test_2, "foo", [], True
        yield self._do_test_2, "foo", ["bar"], False
        yield self._do_test_2, "foo", ["bar"], True
