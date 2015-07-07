#! /usr/bin/env python3

import os
import gzip
import json

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
        self.dbpath = os.path.join(cache_dir, "wiki-scripts", self.api.get_hostname(), self.dbname + ".db.json.gz")
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
            db = gzip.open(self.dbpath, mode="rt", encoding="utf-8")
            self.data = json.loads(db.read())
        else:
            self.init(key)

    def dump(self):
        """
        Save data to disk. When :py:attribute:`self.autocommit` is ``True``, it is
        called automatically from :py:meth:`self.init()` and :py:meth:`self.update()`.

        After manual modification of the ``self.data`` structure it is necessary to
        call it manually if the change is to be persistent.
        """
        # create leading directories
        try:
            os.makedirs(os.path.split(self.dbpath)[0])
        except OSError as e:
            if e.errno != 17:
                raise e

        print("Saving data to {} ...".format(self.dbpath))
        db = gzip.open(self.dbpath, mode="wt", encoding="utf-8")
        db.write(json.dumps(self.data))

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
        pass

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
        pass


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

class ListOfDictsAttrWrapper(object):
    """ A list-like wrapper around list of dicts, operating on a given attribute.
    """
    def __init__(self, dict_list, attr):
        self.dict_list = dict_list
        self.attr = attr
    def __getitem__(self, index):
        return self.dict_list[index][self.attr]
    def __len__(self):
        return self.dict_list.__len__()


from .AllRevisionsProps import *
from .LatestRevisionsText import *

__all__ = ["CacheDb", "ListOfDictsAttrWrapper", "AllRevisionsProps", "LatestRevisionsText"]
