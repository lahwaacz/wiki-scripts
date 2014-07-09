#! /usr/bin/env python3

# flatten _shallow_ list
def flatten_list(iterable):
    return [inner for outer in iterable for inner in outer]

# flatten _shallow_ generator
def flatten_gen(iterable):
    return (inner for outer in iterable for inner in outer)
