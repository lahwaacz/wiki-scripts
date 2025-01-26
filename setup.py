#! /usr/bin/env python3

from setuptools import find_packages, setup

import ws

setup(
    name = "wiki-scripts",
    version = ws.__version__,
    packages = find_packages(),
    install_requires = [
        "requests",
        "mwparserfromhell",
        "configfile",
        "sqlalchemy",
        "psycopg",
        "wikeddiff",
    ],
)
