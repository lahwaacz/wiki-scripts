#! /usr/bin/env python3

"""
:py:func:`RateLimited` is a rate limiting algorithm implemented as Python decorator.

The original algorithm comes from this `StackOverflow answer`_ and has been modified
to apply longer timeout when the rate limit is exceeded.

.. _`StackOverflow answer`: http://stackoverflow.com/a/6415181


Usage as Python decorator:

.. code-block:: python
    # allow at most 10 calls in 2 seconds
    @RateLimited(10, 2)
    def PrintNumber(num):
        print(num)

Or at runtime by wrapping the function call:

.. code-block:: python
    # allow at most 10 calls in 2 seconds
    wrapped = RateLimited(10, 2)(PrintNumber)
"""

import time

def RateLimited(rate, per):
    def decorate(func):
        # globals for the decorator
        # defined as lists to avoid problems with the 'global' keyword
        allowance = [rate]
        last_check = [time.clock()]
        def rate_limit_func(*args,**kargs):
            current = time.clock()
            time_passed = current - last_check[0]
            last_check[0] = current
            allowance[0] += time_passed * (rate / per)
            if allowance[0] > rate:
                allowance[0] = rate    # throttle
            if allowance[0] < 1.0:
                # the original used    to_sleep = (1 - allowance[0]) * (per / rate)
                # but we want longer timeout after burst limit is exceeded
                to_sleep = (1 - allowance[0]) * per
                print("rate limit exceeded, sleeping for %0.3f seconds" % to_sleep)
                time.sleep(to_sleep)
                ret = func(*args,**kargs)
                allowance[0] = rate
            else:
                ret = func(*args,**kargs)
                allowance[0] -= 1.0
            return ret
        return rate_limit_func
    return decorate


if __name__ == "__main__":
    # wrap 'print' in rate limiting
    wrapped = RateLimited(10, 2)(print)

    # this should print 1,2,3... at given rate
    for i in range(1, 100):
        wrapped(i)
