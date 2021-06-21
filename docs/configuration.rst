Configuration
-------------

The scripts in the project's root directory use a configuration interface from
the :py:mod:`ws.config` submodule, which relies on the :py:mod:`argparse` and
:py:mod:`configparser` Python modules.

All options can be passed as command line arguments, the special ``--help`` option
prints all available options for a particular script:

.. code::

    $ python print-namespaces.py -h
    ...

    optional arguments:
      -h, --help            show this help message and exit
      -c PATH_OR_NAME, --config PATH_OR_NAME
                            path to the config file, or a base file name for config files looked up as
                            /home/lahwaacz/.config/wiki-scripts/<name>.conf (default: default)
      --no-config           do not read any config file
      --log-level {debug,info,warning,error,critical}
                            the verbosity level for terminal logging (default: info)
      -d, --debug           shortcut for '--log-level debug'
      -q, --quiet           shortcut for '--log-level warning'

    Connection parameters:
      --api-url URL         the URL to the wiki's api.php
      --index-url URL       the URL to the wiki's index.php
      --connection-max-retries CONNECTION_MAX_RETRIES
                            maximum number of retries for each connection (default: 3)
      --connection-timeout CONNECTION_TIMEOUT
                            connection timeout in seconds (default: 60)
      --cookie-file PATH    path to cookie file (default: None)

The long arguments that start with ``--`` can be set in a configuration file
specified by the ``-c``/``--config`` option. The configuration file uses an
extended INI format as implemented by the :py:mod:`configparser` Python module.
The configuration file contains a key-value pairs, where keys correspond to the
long argument names without the ``--`` prefix. Options from the configuration
file are internally processed by adding them to the command line, so
``debug = true`` in a config file is equivalent to passing ``--debug`` on the
command line. Values passed on the command line take precedence over those
specified in a configuration file.

:Note:

    Although it is possible to set `all` long arguments in a configuration file,
    setting all arguments this way may not be a good idea -- for example setting
    the ``help`` argument from the configuration file does not make sense.

Configuration file location
...........................

The value of the ``-c``/``--config`` option can be either a path to the
configuration file (which must have a ``.conf`` suffix), or a `name` of the
configuration which is looked up in the ``$XDG_CONFIG_HOME/wiki-scripts/``
directory as ``<name>.conf``. The default value of the ``-c``/``--config``
option is ``default``, i.e., the default configuration file path is
``$XDG_CONFIG_HOME/wiki-scripts/default.conf``.

:Tip:

    To quickly switch between default configurations, you can create a symbolic
    link from ``$XDG_CONFIG_HOME/wiki-scripts/default.conf`` to a different
    configuration file.

Configuration file format
.........................

The configuration file contains a top-level ``[DEFAULTS]`` section which
contains global options that are applied to all scripts:

.. code-block:: ini

    # Default options (applicable to all scripts).
    [DEFAULTS]
    api-url = https://wiki.archlinux.org/api.php
    index-url = https://wiki.archlinux.org/index.php
    cookie-file = ~/.local/share/wiki-scripts/ArchWiki.cookie

Options can be applied only to a specific script by defining them in a section
named after the script, i.e., options from the ``[script]`` section are read by
a script named ``script.py``. Options defined in a specific section also
override corresponding options from the ``[DEFAULTS]`` section. For example:

.. code-block:: ini

    # Default options (applicable to all scripts).
    [DEFAULTS]
    api-url = https://wiki.archlinux.org/api.php
    index-url = https://wiki.archlinux.org/index.php
    cookie-file = ~/.local/share/wiki-scripts/ArchWiki.cookie

    # Script-specific options.
    [update-pkg-templates]
    cookie-file = ~/.local/share/wiki-scripts/ArchWiki.bot.cookie

To avoid duplicating option values, :py:mod:`configparser` supports sharing
common parts with the `interpolation syntax`_ (wiki-scripts uses the
:py:class:`~configparser.ExtendedInterpolation` handler). Note that you can also
define custom keys in the configuration file, which do not correspond to
wiki-scripts options, but are used for the interpolation. The previous example
can be simplified into:

.. code-block:: ini

    # Default options (applicable to all scripts).
    [DEFAULTS]
    # custom options for interpolation
    site = ArchWiki
    data-dir = ~/.local/share/wiki-scripts/

    # wiki-scripts options.
    api-url = https://wiki.archlinux.org/api.php
    index-url = https://wiki.archlinux.org/index.php
    cookie-file = ${data-dir}/${site}.cookie

    # Script-specific options.
    [update-pkg-templates]
    cookie-file = ${data-dir}/${site}.bot.cookie

The full example of a configuration file is available as `sample.conf`_.

.. _interpolation syntax: https://docs.python.org/3/library/configparser.html#interpolation-of-values
.. _sample.conf: https://github.com/lahwaacz/wiki-scripts/blob/master/examples/sample.conf

Migrating configuration from pre-2.0 versions
.............................................

Versions up to 1.3 used the `ConfigArgParse`_ and `configfile`_ libraries for
handling configuration, which were replaced with standard Python modules
(:py:mod:`argparse` and :py:mod:`configparser`) in version 2.0. This section
helps users to migrate their configuration for the new implementation.

Firstly, the default path for the ``-c``/``--config`` option is different:

- Old path: ``$XDG_CONFIG_HOME/wiki-scripts/wiki-scripts.conf``
- New path: ``$XDG_CONFIG_HOME/wiki-scripts/default.conf``

Next, the configuration needs to be updated from the `configfile`_ syntax to the
:py:mod:`configparser` syntax. Note that the features supported by these two
libraries differ:

- :py:mod:`configparser` does not support nested sections (subsections),
- `configfile`_ has different syntax for the interpolation of option values than
  :py:mod:`configparser`.

Also note that the ``--site`` and ``--cache-dir`` options have become unused and were
removed. Hence, the main things that will need to be changed are:

- Start the configuration with a ``[DEFAULTS]`` section.
- Avoid nested sections. For example, if you had a configuration for ``--site
  ArchWiki``, move all options from ``[ArchWiki]`` into ``[DEFAULTS]`` and
  remove ``ArchWiki.`` from all sections starting with this prefix.
- Update the interpolation syntax. For example, use ``${option}`` instead of
  ``${option$}``.

The structuring that was previously achieved by the ``--site`` option
can now be done with the ``--config`` option. For example, if you had a
non-default configuration for ``--site Wikipedia``, you can create a
configuration file at ``$XDG_CONFIG_HOME/wiki-scripts/Wikipedia.conf``
containing all former ``[Wikipedia.*]`` sections (but without the
``Wikipedia.`` prefix in section names) and select it with ``--config
Wikipedia``.

For more insights into the migration, you can compare the `sample.conf`_ file
with its `1.3 version
<https://github.com/lahwaacz/wiki-scripts/blob/1.3/examples/sample.conf>`_.

Finally, note that some options may have different behaviour (e.g., different
default value) in the new version compared to version 1.3, but we did not keep
an exact list of differences.

.. _ConfigArgParse: https://github.com/lahwaacz/ConfigArgParse/tree/config_files_without_merging
.. _configfile: https://github.com/kynikos/lib.py.configfile
