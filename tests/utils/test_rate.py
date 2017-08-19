#! /usr/bin/env python3

#from nose.tools import assert_equals, raises, timed, TimeExpired
#
#from ws.utils import RateLimited
#
#def _simple_gen():
#    yield from range(100)
#
#class test_rate:
#    rate = 10
#    step = 0.01
#
#    def setup(self):
#        self.func = RateLimited(self.rate, self.step * 1.5)(_simple_gen)
#
#    @timed(step)
#    def test_1(self):
#        for i in range(self.rate):
#            self.func()
#
#    @raises(TimeExpired)
#    @timed(step)
#    def test_2(self):
#        for i in range(round(self.rate * 1.5)):
#            self.func()
#
#    @timed(step * 2)
#    def test_3(self):
#        for i in range(self.rate * 2):
#            self.func()
#
#    @raises(TimeExpired)
#    @timed(step * 2)
#    def test_4(self):
#        for i in range(round(self.rate * 2.5)):
#            self.func()
