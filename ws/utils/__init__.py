import itertools
from typing import Generator, Iterable

from .base_enc import *
from .containers import *
from .datetime_ import *
from .httpx import *
from .json import *
from .lazy import *
from .OrderedSet import *
from .rate import *


def list_chunks[T](list_: list[T], bs: int) -> Generator[list[T]]:
    """Split ``list_`` into chunks of fixed length ``bs``"""
    return (list_[i : i + bs] for i in range(0, len(list_), bs))


def iter_chunks[T](iterable: Iterable[T], bs: int) -> Generator[Iterable[T]]:
    """
    Yield from ``iterable`` by chunks of fixed length ``bs``

    Based on https://stackoverflow.com/a/24527424
    """
    iterator = iter(iterable)
    for first in iterator:
        yield itertools.chain([first], itertools.islice(iterator, bs - 1))
