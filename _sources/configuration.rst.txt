Configuration
-------------

The scripts in the project's root directory use a configuration interface from
the ``ws.config`` submodule, which relies on the `ConfigArgParse`_ and
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
                            path to config file (default: /home/lahwaacz/.config
                            /wiki-scripts/wiki-scripts.conf)
      --site SITE           sets the top-level section to be read from config
                            files (default: ArchWiki)
      --log-level {debug,info,warning,error,critical}
                            the verbosity level for terminal logging (default:
                            info)
      -d, --debug           shorthand for '--log-level debug'
      -q, --quiet           shorthand for '--log-level warning'
      --tmp-dir PATH        temporary directory path (will be created if
                            necessary, but parent directory must exist) (default:
                            /tmp/wiki-scripts)
      --cache-dir PATH      directory for storing cached data (will be created if
                            necessary, but parent directory must exist) (default:
                            /home/lahwaacz/.cache/wiki-scripts)

    Connection parameters:
      --api-url URL         the URL to the wiki's api.php (default:
                            https://wiki.archlinux.org/api.php)
      --index-url URL       the URL to the wiki's api.php (default:
                            https://wiki.archlinux.org/index.php)
      --ssl-verify {0,1}    whether to verify SSL certificates (default: 1)
      --cookie-file PATH    path to cookie file (default: $cache_dir/$site.cookie)

:Note:

    The fact that ``--help`` shows an argument does not necessarily mean that
    its value is used by the script in question (for example
    ``print-namespaces.py`` does not use the ``--tmp-dir`` and ``--cache-dir``
    arguments).

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
