#! /usr/bin/env python3

from collections import OrderedDict

class DeferrableExecutionQueue:
    """
    TODO: add description

    Note: if multiple different statements are being deferred, their queues are
    executed in the same order they were added, so statements from the second
    queue can depend on the statements from the first queue and so on. As soon
    as the size of any queue reaches the size limit, all queues are executed -
    otherwise the queues may get out of sync and execution may hit constraint
    errors.
    """
    def __init__(self, conn, chunk_size):
        if chunk_size <= 0:  # pragma: no cover
            raise ValueError("chunk_size must be positive")

        self.conn = conn
        self.chunk_size = chunk_size

        self.stmt_queues = OrderedDict()

    def execute(self, statement, *multiparams, **params):
        """
        should mimic sqlalchemy's conn.execute, but with deferring
        """
        if self.chunk_size == 1:
            self.conn.execute(statement, *multiparams, **params)
        else:
            q = self.stmt_queues.setdefault(statement, [])
            if multiparams:
                q += multiparams
            if params:
                q.append(params)

            if len(q) >= self.chunk_size:
                self.execute_deferred()

    def execute_deferred(self):
        for statement, values in self.stmt_queues.items():
            self.conn.execute(statement, values)
        self.stmt_queues.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.execute_deferred()
