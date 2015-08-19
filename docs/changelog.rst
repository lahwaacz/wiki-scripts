Changelog
=========

Version 1.0
-----------

`Released August 19, 2015 <https://github.com/lahwaacz/wiki-scripts/tree/1.0>`_
(`changes <https://github.com/lahwaacz/wiki-scripts/compare/0.6...1.0>`__)

- Major reorganization of the project structure: common code shared between the
  scripts has been moved to the :py:mod:`ws` module and the original
  :py:mod:`MediaWiki` module has been renamed to :py:mod:`ws.core`, some of its
  parts were moved directly to :py:mod:`ws`.
- Reorganization of the :py:mod:`ws.parser_helpers` submodule, added
  :py:mod:`ws.parser_helpers.encodings`.
- Expanded documentation, fixed many typos in docstrings.
- Expanded test suite, at least for parts not depending on the MediaWiki API.
- Generalized the :py:class:`ws.core.connection.Connection` class to handle also
  the ``index.php`` entry point.
- Created the :py:class:`ws.core.lazy.LazyProperty` decorator and made
  :py:attr:`ws.core.api.API.is_loggedin`, :py:attr:`ws.core.api.API.user_rights`
  and :py:attr:`ws.core.api.API.namespaces` proper properties.
- Started using the :py:mod:`logging` module for messages.
- New unified configuration interface for all scripts, using the
  :py:mod:`ws.config` submodule. See `Configuration <configuration>`_ for
  details.

  - Basically all scripts were modified to use the :py:mod:`ws.config`
    interface.
  - Default cookie path was changed from ``$XDG_CACHE_HOME`` to
    ``$XDG_CACHE_HOME/wiki-scripts``.
  - Some command line arguments were renamed because of global configuration in
    a config file.

- Added also ``assert=bot`` to all bot editing queries.
- Fixed bugs:
  
  - formatting of streak timestamps in the ``statistic.py`` script,
  - namespace prefix parsing in :py:meth:`ws.core.api.API.detect_namespace`,
  - extraction of header elements in case they are nested inside e.g.
    ``<noinclude>`` tags,
  - whitespace squashing in the
    :py:func:`ws.parser_helpers.wikicode.remove_and_squash` function,
  - query-continuation algorithm (used to fail with generator queries with
    multiple values in the ``prop`` query parameter),
  - JSON serialization of non-str keys,
  - exception catching for opening cookies,
  
- Improved scripts:

  - ``statistics.py`` (minor bug fixes)
  - ``update-interlanguage-links.py`` (heavy refactoring)
  - ``check-user-namespace.py`` (warn if user pages are categorized)
  - ``list-redirects-broken-fragments.py`` (improved detection of redirects with
    broken fragments by comparing dot-encoded fragments)
  - ``dump.py`` (deduplicated against :py:class:`ws.core.connection.Connection`)

- New scripts:

  - ``recategorize-over-redirect.py``

