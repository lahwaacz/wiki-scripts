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

    @classmethod
    def filter_params(klass, params, *, generator=False):
        new_params = {}
        for key, value in params.items():
            prefix = klass.API_PREFIX
            if generator is True:
                prefix = "g" + prefix
            if key.startswith(prefix):
                new_key = key[len(prefix):]
                new_params[new_key] = value
        return new_params

    def execute_sql(self, query, *, explain=False):
        with self.db.engine.connect() as conn:
            if explain is True:
                from ws.db.database import explain
                result = conn.execute(explain(query))
                print(query)
                for row in result:
                    print(row[0])

            return conn.execute(query)
