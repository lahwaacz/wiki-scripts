import itertools

from .base_enc import *
from .containers import *
from .datetime_ import *
from .httpx import *
from .json import *
from .lazy import *
from .OrderedSet import *
from .rate import *


# split ``list_`` into chunks of fixed length ``bs``
def list_chunks(list_, bs):
    return (list_[i: i + bs] for i in range(0, len(list_), bs))

# yield from ``iterable`` by chunks of fixed length ``bs``
# adjusted from http://stackoverflow.com/questions/24527006/split-a-generator-into-chunks-without-pre-walking-it/24527424#24527424
def iter_chunks(iterable, bs):
    iterator = iter(iterable)
    for first in iterator:
        yield itertools.chain([first], itertools.islice(iterator, bs - 1))
