#! /usr/bin/env python3

# TODO:
#   include timestamp in all databases (updated transparently in CacheDb.dump, could be just the modification timestamp on the file)
#   hash the JSON before writing to disk, verify when loading
#   compression level should be configurable, as well as compression format (e.g. optional dependency on python-lz4)

import os
import gzip
import json
import hashlib

def md5sum(bytes_):
    h = hashlib.md5()
    h.update(bytes_)
    return h.hexdigest()

class CacheDb:
    """
    Base class for caching databases. The database is saved on disk in the
    gzipped JSON format. The data is represented by the ``self.data`` structure,
    whose type depends on the implementation in each subclass (generally a
    ``list`` or ``dict``).

    The database is initialized lazily from the accessors
    :py:meth:`self.__getitem__()`, :py:meth:`self.__iter__()`,
    :py:meth:`self.__reversed__()` and :py:meth:`self.__contains__()`.

    :param api: an :py:class:`MediaWiki.API` instance
    :param dbname: a name of the database (``str``), usually the name of the
                   subclass
    :param autocommit: whether to automatically call :py:meth:`self.dump()`
                       after each update of the database
    """
    def __init__(self, api, dbname, autocommit=True):
        self.api = api
        self.dbname = dbname
        self.autocommit = autocommit

        cache_dir = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
        dbdir = os.path.join(cache_dir, "wiki-scripts", self.api.get_hostname())
        self.dbpath = os.path.join(dbdir, self.dbname + ".db.json.gz")
        self.hashpath = os.path.join(dbdir, self.dbname + ".md5sum")

        self.data = None

    def load(self, key=None):
        """
        Try to load data from disk. When data on disk does not exist yet, calls
        :py:meth:`self.init()` to initialize the database and :py:meth:`self.dump()`
        immediately after to save the initial state to disk.

        Called automatically from :py:meth:`self.__init__()`, it is not necessary to call it manually.

        :param key: passed to :py:meth:`self.init()`, necessary for proper lazy
                    initialization in case of multi-key database
        """
        if os.path.isfile(self.dbpath):
            print("Loading data from {} ...".format(self.dbpath))
            db = gzip.open(self.dbpath, mode="rb")
            s = db.read()

            if os.path.isfile(self.hashpath):
                # TODO: make md5 hash mandatory at some point
                md5_new = md5sum(s)
                # assumes there is only one md5sum in the file
                md5_old = open(self.hashpath, mode="rt", encoding="utf-8").read().split()[0]
                if md5_new != md5_old:
                    raise CacheDbError("md5sums of the database {} differ. Please investigate...".format(self.dbpath))

            self.data = json.loads(s.decode("utf-8"))
        else:
            self.init(key)

    def dump(self):
        """
        Save data to disk. When :py:attribute:`self.autocommit` is ``True``, it is
        called automatically from :py:meth:`self.init()` and :py:meth:`self.update()`.

        After manual modification of the ``self.data`` structure it is necessary to
        call it manually if the change is to be persistent.
        """
        print("Saving data to {} ...".format(self.dbpath))

        # create leading directories
        try:
            os.makedirs(os.path.split(self.dbpath)[0])
        except OSError as e:
            if e.errno != 17:
                raise e

        s = json.dumps(self.data).encode("utf-8")
        md5 = md5sum(s)
        db = gzip.open(self.dbpath, mode="wb", compresslevel=3)
        db.write(s)
        hashf = open(self.hashpath, mode="wt", encoding="utf-8")
        hashf.write("{}  {}\n".format(md5, self.dbname + ".db.json"))

    def init(self, key=None):
        """
        Called by :py:meth:`self.load()` when data does not exist on disk yet.
        Responsible for initializing ``self.data`` structure and performing
        the initial API query.

        Responsible for calling :py:meth:`self.dump()` after the query depending
        on the value of :py:attribute:`self.autocommit`.
        
        Has to be defined in subclasses.

        :param key: database key determining which part of the database should be
                    initialized. Can be ignored in case of single-key databases.
        """
        raise NotImplementedError

    def update(self, key=None):
        """
        Method responsible for updating the cached data, called from all accessors
        :py:meth:`self.__getitem__()`, :py:meth:`self.__iter__()`,
        :py:meth:`self.__reversed__()` and :py:meth:`self.__contains__()`.

        Responsible for calling :py:meth:`self.dump()` after the query depending
        on the value of :py:attribute:`self.autocommit`.
        
        Has to be defined in subclasses.

        :param key: database key determining which part of the database should be
                    initialized. Can be ignored in case of single-key databases.
        """
        raise NotImplementedError


    # TODO: make some decorator to actually run the code only every minute or so
    #       ...or maybe not necessary. The accessed data is mutable anyway, so
    #       the accessors are not actually called very often -- at least for dict.
    def _load_and_update(self, key=None):
        """
        Helper method called from the accessors.
        """
        if self.data is None:
            self.load(key)
        self.update(key)

    def __getitem__(self, key):
        self._load_and_update(key)
        return self.data.__getitem__(key)

    # TODO: write access to top-level items should never be necessary, might compromise the database
#    def __setitem__(self, key, value):
#        self._load_and_update()
#        return self.data.__setitem__(key, value)

    def __iter__(self):
        self._load_and_update()
        return self.data.__iter__()

    def __reversed__(self):
        self._load_and_update()
        return self.data.__reversed__()

    def __contains__(self, item):
        self._load_and_update(item)
        return self.data.__contains__(item)

class CacheDbError(Exception):
    """ Raised on database errors, e.g. when loading from disk failed.
    """
    pass


from .AllRevisionsProps import *
from .LatestRevisionsText import *

__all__ = ["CacheDb", "CacheDbError", "AllRevisionsProps", "LatestRevisionsText"]
