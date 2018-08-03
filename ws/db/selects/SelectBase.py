#!/usr/bin/env python3

class SelectBase:

    API_PREFIX = None
    DB_PREFIX = None

    def __init__(self, db):
        self.db = db

    @classmethod
    def set_defaults(klass, params):
        """
        Responsible for setting default values of the query parameters.
        """
        raise NotImplementedError

    @classmethod
    def sanitize_params(klass, params):
        """
        Responsible for raising :py:exc:`AssertionError` in case of wrong input.
        """
        raise NotImplementedError

    @classmethod
    def db_to_api(klass, row):
        """
        Converts data from the database into the API format.
        """
        raise NotImplementedError

    def execute_sql(self, query, *, explain=False):
        if explain is True:
            from ws.db.database import explain
            result = self.db.engine.execute(explain(query))
            print(query)
            for row in result:
                print(row[0])

        return self.db.engine.execute(query)
