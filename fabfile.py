#! /usr/bin/env python2
# -*- coding: utf-8 -*-

from fabric.api import *

@task
def build_docs():
    module = "ws"
    local("sphinx-apidoc --separate --module-first --force --no-toc --output-dir ./docs/{0}/ {0}".format(module))
    with lcd("./docs/"):
        local("make clean")
        local("make html")
    # recreate the git submodule files (deleted with make clean)
    git = open("./docs/_build/html/.git", "w")
    git.write("gitdir: ../../../.git/modules/gh-pages\n")
    local("touch ./docs/_build/html/.nojekyll")

@task
def deploy_docs():
    build_docs()
    with lcd("./docs/_build/html/"):
        local("git add .")
        msg = raw_input("Enter commit message: ")
        local("git commit -m '%s'" % msg)
        local("git push")
