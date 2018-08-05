Changelog
=========

Version 1.3
-----------

Unreleased
(`changes <https://github.com/lahwaacz/wiki-scripts/compare/1.2...master>`__)

- SQL database:
    - Implemented a subset of MediaWiki API querie. Lists: ``allpages``,
      ``alldeletedrevisions``, ``allrevisions``, ``logevents``,
      ``protectedtitles``, ``recentchanges``; props: ``deletedrevisions``,
      ``revisions``, ``pageprops``; including ``generator``, ``titles`` and
      ``pageids`` parameters. See the GitHub issue for more information:
      https://github.com/lahwaacz/wiki-scripts/issues/35.
    - Implemented synchronization of the latest revisions contents.
    - Fixed many bugs in the synchronization process.
- Removed :py:mod:`ws.cache.LatestRevisions` module. Scripts use the SQL
  database for caching.
- Merged several smaller scripts into ``list-problems.py``.

Version 1.2
-----------

`Released December 31, 2017 <https://github.com/lahwaacz/wiki-scripts/tree/1.2>`_
(`changes <https://github.com/lahwaacz/wiki-scripts/compare/1.1...1.2>`__)

- Large refactoring: :py:mod:`ws.core` renamed to :py:mod:`ws.client`, created
  :py:mod:`ws.utils`, :py:mod:`ws.statistics`, :py:mod:`ws.interlanguage`
- Added :py:mod:`ws.client.site`, :py:mod:`ws.client.user` and
  :py:mod:`ws.client.redirects` modules, :py:class:`ws.client.api.API` has
  attributes with the appropriate instances for the current wiki.
- Improved parsing of page titles -- fixed many bugs, extended test suite, added
  checking of legal characters, handling of namespace aliases.
- Added :py:mod:`ws.autopage` submodule.
- Switched from :py:mod:`nose` to :py:mod:`pytest` for testing.
- Added :py:mod:`ws.db` module for the synchronization of a remote wiki into a
  local PostgreSQL database. See the GitHub issue for more information:
  https://github.com/lahwaacz/wiki-scripts/issues/35. This also means multiple
  new dependencies, see the README file for details.
- Transparent automatic conversion of timestamp strings into the Python's
  :py:mod:`datetime.datetime` objects. As a result, manual calls to the
  :py:func:`ws.utils.parse_date` and :py:func:`ws.utils.format_date` functions
  should not be necessary when working with the API.

Version 1.1
-----------

`Released March 6, 2016 <https://github.com/lahwaacz/wiki-scripts/tree/1.1>`_
(`changes <https://github.com/lahwaacz/wiki-scripts/compare/1.0...1.1>`__)

- Fixed handling of ``csrftoken``, it is now cached and automatically renewed as
  indicated by the server responses.
- Partial interlanguage support for ``update-package-templates.py``: localized
  templates "Broken package link" and "aur-mirror" are respected.
- Added the :py:mod:`ws.parser_helpers.title` module for parsing titles into
  ``(iwprefix, namespace, pagename, sectionname)`` and easy manipulation with
  the parts.
- Removed :py:meth:`ws.core.api.API.detect_namespace()` in favour of the new
  :py:class:`Title <ws.parser_helpers.title.Title>` parser.
- Improved exception logging in :py:meth:`API.edit() <ws.core.api.API.edit>`.
  Both :py:meth:`ws.core.api.API.edit()` and
  :py:func:`ws.interactive.edit_interactive()` now take an additional ``title``
  parameter representing the title of the page being edited.
- Added support for :py:mod:`WikEdDiff`, an inline-style diff engine with
  block move support and splitting optimized for MediaWiki markup.
  :py:mod:`pygments` is now used only as a fallback.
- The ``link-checker.py`` script has been improved to consider the
  ``DISPLAYTITLE`` property of pages and links to sections are checked base on
  the sections existing on the target page.
- Added ``--connection-max-retries`` and ``--connection-timeout`` options.
- Added ``toc.py`` script to update the "Table of contents" page on the wiki.

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
  
  - formatting of streak timestamps in the ``statistic.py`` script
  - namespace prefix parsing in :py:meth:`ws.core.api.API.detect_namespace`
  - extraction of header elements in case they are nested inside e.g.
    ``<noinclude>`` tags
  - whitespace squashing in the
    :py:func:`ws.parser_helpers.wikicode.remove_and_squash` function
  - query-continuation algorithm (used to fail with generator queries with
    multiple values in the ``prop`` query parameter)
  - JSON serialization of non-str keys
  - exception catching for opening cookies
  
- Improved scripts:

  - ``statistics.py`` (minor bug fixes)
  - ``update-interlanguage-links.py`` (heavy refactoring)
  - ``check-user-namespace.py`` (warn if user pages are categorized)
  - ``list-redirects-broken-fragments.py`` (improved detection of redirects with
    broken fragments by comparing dot-encoded fragments)
  - ``dump.py`` (deduplicated against :py:class:`ws.core.connection.Connection`)

- New scripts:

  - ``recategorize-over-redirect.py``

