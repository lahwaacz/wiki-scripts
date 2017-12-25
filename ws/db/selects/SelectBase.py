#!/usr/bin/env python3

class SelectBase:

    API_PREFIX = None
    DB_PREFIX = None

    def __init__(self, db):
        self.db = db

    @staticmethod
    def set_defaults(params):
        """
        Responsible for setting default values of the query parameters.
        """
        raise NotImplementedError

    @staticmethod
    def sanitize_params(params):
        """
        Responsible for raising :py:exc:`AssertionError` in case of wrong input.
        """
        raise NotImplementedError

    @staticmethod
    def db_to_api(row):
        """
        Converts data from the database into the API format.
        """
        raise NotImplementedError

    def list(self, params):
        """
        Generator which yields the results of the query.

        :param dict params: query parameters
        """
        self.set_defaults(params)
        self.sanitize_params(params)

        s = self.get_select(params)

        # TODO: some lists like allrevisions should group the results per page like MediaWiki
        result = self.db.engine.execute(s)
        for row in result:
            yield self.db_to_api(row)
        result.close()
