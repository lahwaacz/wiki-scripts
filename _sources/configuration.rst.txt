Configuration
-------------

The scripts in the project's root directory use a configuration interface from
the :py:mod:`ws.config` submodule, which relies on the `ConfigArgParse`_ and
`configfile`_ libraries.

.. _ConfigArgParse: https://github.com/lahwaacz/ConfigArgParse/tree/config_files_without_merging
.. _configfile: https://github.com/kynikos/lib.py.configfile

All options can be passed as command line arguments, the special ``--help`` option
prints all available options for a script:

.. code::

    $ python print-namespaces.py -h
    ...

    optional arguments:
      -h, --help            show this help message and exit
      -c PATH, --config PATH
                            path to config file (default:
                            /home/lahwaacz/.config/wiki-scripts/wiki-scripts.conf)
      --site SITE           sets the top-level section to be read from config
                            files (default: ArchWiki)
      --log-level {debug,info,warning,error,critical}
                            the verbosity level for terminal logging (default:
                            info)
      -d, --debug           shortcut for '--log-level debug'
      -q, --quiet           shortcut for '--log-level warning'
      --cache-dir PATH      directory for storing cached data (will be created if
                            necessary, but parent directory must exist) (default:
                            /home/lahwaacz/.cache/wiki-scripts)

    Connection parameters:
      --api-url URL         the URL to the wiki's api.php (default:
                            https://wiki.archlinux.org/api.php)
      --index-url URL       the URL to the wiki's api.php (default:
                            https://wiki.archlinux.org/index.php)
      --ssl-verify SSL_VERIFY
                            whether to verify SSL certificates (default: True)
      --connection-max-retries CONNECTION_MAX_RETRIES
                            maximum number of retries for each connection
                            (default: 3)
      --connection-timeout CONNECTION_TIMEOUT
                            connection timeout in seconds (default: 30)
      --cookie-file PATH    path to cookie file (default: $cache_dir/$site.cookie)

The long arguments that start with ``--`` can be set in a configuration file
specified by the ``--config`` option. The configuration file uses an extended INI
format to specify a ``(key, value)`` pairs, where ``key`` corresponds to the long
argument name without the ``--`` prefix. Options from the configuration file are
internally processed by adding them to the command line, so ``debug = true`` in a
config file is equivalent to passing ``--debug`` on the command line. Values
passed on the command line take precedence over those specified in a
configuration file.

:Note:

    Although it is possible to set _all_ long arguments in a configuration file,
    setting all arguments this way may not be a good idea -- for example setting
    the ``help`` argument from the configuration file does not make sense.

Configuration file format
.........................

It is important to note that all argument keys in a configuration file are
global and shared by all scripts, but can be structured into multiple sections
to allow better flexibility over setting all options in the top-level section.
The ``--site`` argument specifies the section to be read from the configuration
file, e.g. ``--site ArchWiki`` selects the ``[ArchWiki]`` section. This allows
maintaining a configuration file for multiple sites, for example

.. code-block:: ini

    site = ArchWiki-de

    [ArchWiki]
    api-url = https://wiki.archlinux.org/api.php
    index-url = https://wiki.archlinux.org/index.php

    [ArchWiki-de]
    api-url = https://wiki.archlinux.de/api.php
    index-url = https://wiki.archlinux.de/index.php

The global option ``site`` can be set in the configuration file to set different
default site, which can be overridden with ``--site ArchWiki`` on the command
line.

To override the site options on a per-script basis, it is possible to create a
``[sitename.scriptname]`` subsections, which inherit all options from the parent 
section. For example:

.. code-block:: ini

    site = ArchWiki

    [ArchWiki]
    api-url = https://wiki.archlinux.org/api.php
    index-url = https://wiki.archlinux.org/index.php
    cookie-file = ~/.cache/wiki-scripts/ArchWiki.cookie

    [ArchWiki.update-pkg-templates]
    cookie-file = ~/.cache/wiki-scripts/ArchWiki.bot.cookie

To avoid duplicating option values, `configfile`_ supports sharing common parts
with the `interpolation syntax`_. The previous example can be simplified into:

.. code-block:: ini

    site = ArchWiki

    cache-dir = ~/.cache/wiki-scripts/

    [ArchWiki]
    api-url = https://wiki.archlinux.org/api.php
    index-url = https://wiki.archlinux.org/index.php
    cookie-file = ${cache-dir$}/ArchWiki.cookie

    [ArchWiki.update-pkg-templates]
    cookie-file = ${cache-dir$}/ArchWiki.bot.cookie

The full example of a configuration file is available as `sample.conf`_.

.. _interpolation syntax: https://kynikos.github.io/lib.py.configfile/#interpolation
.. _sample.conf: https://github.com/lahwaacz/wiki-scripts/blob/master/examples/sample.conf

Database configuration settings
...............................

Some scripts require access to a PostgreSQL database to be configured via the
following options:

.. code-block:: none

    ...

    Database parameters:
      --db-dialect DIALECT  an SQL dialect (default: None)
      --db-driver DRIVER    a driver for given SQL dialect supported by sqlalchemy (default:
                            None)
      --db-user USER        username for database connection (default: None)
      --db-password PASSWORD
                            password for database connection (default: None)
      --db-host HOST        hostname of the database server (default: None)
      --db-port PORT        port on which the database server listens (default: None)
      --db-name DATABASE    name of the database (default: None)

For convenience, these options should can be set in the configuration file.
Note that ``db-name`` must be different for every site. For example:

.. code-block:: ini

    ...

    db-dialect = postgresql
    db-driver = psycopg2

    db-user = wiki-scripts
    db-password = password
    db-host = localhost

    [ArchWiki]
    db-name = ws_archwiki
    ...
