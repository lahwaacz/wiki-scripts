#! /usr/bin/env python3

from setuptools import setup, find_packages

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
        "pymysql",
        "wikeddiff",
    ],
)
