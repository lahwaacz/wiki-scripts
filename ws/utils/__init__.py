#! /usr/bin/env python3

import itertools

from .base_enc import *
from .containers import *
from .datetime_ import *
from .lazy import *
from .rate import *

# test if given string is ASCII
def is_ascii(text):
    try:
        text.encode("ascii")
        return True
    except:
        return False

# split ``list_`` into chunks of fixed length ``bs``
def list_chunks(list_, bs):
    return (list_[i: i + bs] for i in range(0, len(list_), bs))

# yield from ``iterable`` by chunks of fixed length ``bs``
# adjusted from http://stackoverflow.com/questions/24527006/split-a-generator-into-chunks-without-pre-walking-it/24527424#24527424
def iter_chunks(iterable, bs):
    iterator = iter(iterable)
    for first in iterator:
        yield itertools.chain([first], itertools.islice(iterator, bs - 1))

def value_or_none(value):
    if not value:
        return None
    return value
