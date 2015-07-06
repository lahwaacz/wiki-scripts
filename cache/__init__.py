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
    """
    def __init__(self, api, dbname):
        self.api = api
        self.dbname = dbname
        cache_dir = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
        self.dbpath = os.path.join(cache_dir, "wiki-scripts", self.api.get_hostname(), self.dbname + ".db.json.gz")
        self.data = None

    def load(self):
        """
        Try to load data from disk. When data on disk does not exist yet, calls
        :py:meth:`self.init()` to initialize the database and :py:meth:`self.dump()`
        immediately after to save the initial state to disk.

        Called automatically from :py:meth:`self.__init__()`, it is not necessary to call it manually.
        """
        if os.path.isfile(self.dbpath):
            db = gzip.open(self.dbpath, mode="rt", encoding="utf-8")
            self.data = json.loads(db.read())
        else:
            self.init()

    def dump(self):
        """
        Save data to disk. Called automatically from :py:meth:`self.init()` and
        :py:meth:`self.update()`.

        After manual modification of the ``self.data`` structure it is necessary to
        call it manually if the change is to be persistent.
        """
        # create leading directories
        try:
            os.makedirs(os.path.split(self.dbpath)[0])
        except OSError as e:
            if e.errno != 17:
                raise e

        db = gzip.open(self.dbpath, mode="wt", encoding="utf-8")
        db.write(json.dumps(self.data))

    def init(self):
        """
        Called by :py:meth:`self.load()` when data does not exist on disk yet.
        Responsible for initializing ``self.data`` structure and performing
        the initial API query.

        Responsible for calling :py:meth:`self.dump()` after the query.
        
        Has to be defined in subclasses.
        """
        pass

    def update(self):
        """
        Method responsible for updating the cached data, called from all accessors
        :py:meth:`self.__getitem__()`, :py:meth:`self.__iter__()`,
        :py:meth:`self.__reversed__()` and :py:meth:`self.__contains__()`.

        Responsible for calling :py:meth:`self.dump()` after the query.
        
        TODO: note on decorator for time-based caching

        Has to be defined in subclasses.
        """
        pass


    # TODO: make some decorator to actually run the code only every minute or so
    #       ...or maybe not necessary. The accessed data is mutable anyway, so
    #       the accessors are not actually called very often -- at least for dict.
    def _load_and_update(self):
        """
        Helper method called from the accessors.
        """
        if self.data is None:
            self.load()
        self.update()

    def __getitem__(self, key):
        self._load_and_update()
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
        self._load_and_update()
        return self.data.__contains__(item)


from .AllRevisionsProps import *

__all__ = ["CacheDb", "AllRevisionsProps"]
