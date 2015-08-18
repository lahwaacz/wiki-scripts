#! /usr/bin/env python2
# -*- coding: utf-8 -*-

from fabric.api import *

@task
def build_docs():
    module = "ws"
    local("sphinx-apidoc --separate --module-first --force --maxdepth 6 --output-dir ./docs/{0}/ {0}".format(module))
    with lcd("./docs/"):
        local("make clean")
        local("make html")
