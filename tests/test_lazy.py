#! /usr/bin/env python3

from nose.tools import assert_equals

from ws.core.lazy import LazyProperty

class test_lazy:
    def setup(self):
        self._values = list(range(10))

    @LazyProperty
    def lazyprop(self):
        return self._values.pop(0)

    @property
    def normalprop(self):
        return self._values.pop(0)

    def test_lazyprop(self):
        assert_equals(self.lazyprop, 0)
        assert_equals(self.lazyprop, 0)
        del self.lazyprop
        assert_equals(self.lazyprop, 1)
        assert_equals(self.lazyprop, 1)

    def test_normalprop(self):
        assert_equals(self.normalprop, 0)
        assert_equals(self.normalprop, 1)
        assert_equals(self.normalprop, 2)
        assert_equals(self.normalprop, 3)
