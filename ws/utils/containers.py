import bisect
import datetime
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Generator, Iterable, MutableSequence, overload

from .datetime_ import format_date, parse_date

if TYPE_CHECKING:
    from _typeshed import SupportsDunderLT


class ListOfDictsAttrWrapper(Sequence):
    """A list-like wrapper around list of dicts, operating on a given attribute."""

    def __init__(self, dict_list: list[dict], attr: Any):
        self.dict_list = dict_list
        self.attr = attr

    @overload
    def __getitem__(self, index: int) -> Any: ...

    @overload
    def __getitem__(self, index: slice) -> "ListOfDictsAttrWrapper": ...

    def __getitem__(self, index, /):
        if isinstance(index, slice):
            return ListOfDictsAttrWrapper(self.dict_list[index], self.attr)
        return self.dict_list[index][self.attr]

    def __len__(self) -> int:
        return self.dict_list.__len__()


def bisect_find[
    T: "SupportsDunderLT"
](data_list: Sequence[T], key: T, index_list: Sequence[T] | None = None) -> T:
    """
    Find an element in a sorted list using the bisect method.

    :param data_list: list of elements to be returned from
    :param key: element to be found in ``index_list``
    :param index_list: an optional list of indexes where ``key`` is searched for,
                       by default ``data_list`` is taken. Has to be sorted.
    :returns: ``data_list[i]`` if ``index_list[i] == key``
    :raises IndexError: when ``key`` is not found
    """
    index_list = data_list if index_list is None else index_list
    i = bisect.bisect_left(index_list, key)
    if i != len(index_list) and index_list[i] == key:
        return data_list[i]
    raise IndexError(repr(key))


def bisect_insert_or_replace[
    T: "SupportsDunderLT"
](
    data_list: MutableSequence[T],
    key: T,
    data_element: T | None = None,
    index_list: Sequence[T] | None = None,
) -> None:
    """
    Insert an element into a sorted list using the bisect method. If an element
    is found in the list, it is replaced.

    :param data_list: list of elements to be inserted into
    :param data_element: an element to be inserted. By default ``key`` is taken.
    :param key: a key used for searching
    :param index_list: an optional list of indexes where ``key`` is searched for,
                       by default ``data_list`` is taken. Has to be sorted.
    """
    data_element = key if data_element is None else data_element
    index_list = data_list if index_list is None else index_list
    i = bisect.bisect_left(index_list, key)
    if i != len(index_list) and index_list[i] == key:
        data_list[i] = data_element
    else:
        data_list.insert(i, data_element)


def dmerge(source: dict, destination: dict) -> dict:
    """
    Deep merging of dictionaries.
    """
    if not isinstance(source, dict) or not isinstance(destination, dict):
        raise TypeError("both 'source' and 'destination' must be of type 'dict'")
    for key, value in source.items():
        if isinstance(value, dict):
            node = destination.setdefault(key, {})
            dmerge(value, node)
        elif isinstance(value, list):
            node = destination.setdefault(key, [])
            node.extend(value)
        else:
            destination[key] = value

    return destination


def find_caseless(what: str, where: Iterable[str], from_target: bool = False) -> str:
    """
    Do a case-insensitive search in a list/iterable.

    :param what: element to be found
    :param where: a list/iterable for searching
    :param from_target: if True, return the element from the list/iterable instead of ``what``
    :raises ValueError: when not found
    """
    _what = what.lower()
    for item in where:
        if item.lower() == _what:
            if from_target is True:
                return item
            return what
    raise ValueError


def gen_nested_values(
    indict: dict | list | tuple, keys: list | None = None
) -> Generator[tuple[list, Any]]:
    """
    Generator yielding all values stored in a nested structure of dicts, lists
    and tuples.
    """
    keys = keys[:] if keys else []
    if isinstance(indict, dict):
        for key, value in indict.items():
            yield from gen_nested_values(value, keys=keys + [key])
    elif isinstance(indict, list) or isinstance(indict, tuple):
        for i, value in enumerate(indict):
            yield from gen_nested_values(value, keys=keys + [i])
    else:
        yield keys, indict


def parse_timestamps_in_struct(struct: dict | list) -> None:
    """
    Convert all timestamps in a nested structure from ``str`` to
    ``datetime.datetime``.
    """

    def set_ts(struct, keys, value):
        for k in keys[:-1]:
            struct = struct[k]
        struct[keys[-1]] = value

    for keys, value in gen_nested_values(struct):
        if isinstance(value, str):
            # skip fields which are not timestamps (e.g. user=infinity)
            _strkeys = "".join(str(k) for k in keys)
            if (
                "timestamp" not in _strkeys
                and "registration" not in _strkeys
                and "expiry" not in _strkeys
                and "touched" not in _strkeys
            ):
                continue

            if value.lower() == "infinity" or value.lower() == "infinite":
                set_ts(struct, keys, datetime.datetime.max)
            elif value.lower() == "-infinity":
                set_ts(struct, keys, datetime.datetime.min)
            elif value.lower() == "indefinite":
                set_ts(struct, keys, None)
            elif (
                len(value) == 20
                and value[4] == "-"
                and value[7] == "-"
                and value[10] == "T"
                and value[13] == ":"
                and value[16] == ":"
                and value[19] == "Z"
            ):
                try:
                    ts = parse_date(value)
                except ValueError:
                    continue
                set_ts(struct, keys, ts)


def serialize_timestamps_in_struct(struct: dict | list) -> None:
    """
    Convert all timestamps in a nested structure from ``datetime.datetime`` to
    ``str``.
    """

    def set_ts(struct, keys, value):
        for k in keys[:-1]:
            struct = struct[k]
        struct[keys[-1]] = value

    for keys, value in gen_nested_values(struct):
        if isinstance(value, datetime.datetime):
            set_ts(struct, keys, format_date(value))
