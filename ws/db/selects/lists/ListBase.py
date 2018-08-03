#!/usr/bin/env python3

from ..SelectBase import SelectBase

class ListBase(SelectBase):
    def get_select(self, params):
        """
        Returns the SQL query for given parameters to the ``list=`` module.
        """
        raise NotImplementedError
