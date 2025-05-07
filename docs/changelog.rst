Changelog
=========

Version 2.0
-----------

Unreleased
(`changes <https://github.com/lahwaacz/wiki-scripts/compare/1.4...master>`__)

- Project structure refactoring:
  - Added `pyproject.toml` and modern tooling (ruff, mypy)
  - Added `.editorconfig`
- Fixed issues reported by new linters
- Added type hints (PEP 484)
- Tests:
  - Reimplemented pytest fixtures for local MediaWiki testing
  - Added test dependencies: `pytest-docker`, `pytest-dotenv`, `pytest-httpx`
- :py:mod:`ws.checkers`:
  - Dropped obsolete "HTTPS Everywhere" list and implementation
- Switched from the :py:mod:`requests` package to :py:mod:`httpx`
  - New dependencies: :py:mod:`httpx-retries`, :py:mod:`truststore`

Version 1.4
-----------

`Released Apr 27, 2025 <https://github.com/lahwaacz/wiki-scripts/tree/1.4>`_
(`changes <https://github.com/lahwaacz/wiki-scripts/compare/1.3...1.4>`__)

- Replaced the third-party modules ``ConfigArgParse`` and ``configfile`` with
  their built-in alternatives. See the merge request for details:
  https://github.com/lahwaacz/wiki-scripts/pull/69
- As a result, the configuration file format has changed. See `Configuration
  <configuration.html>`_ for details on migrating your configuration.
- The default value of the ``--cookie-file`` option was removed, so it has to be
  set explicitly in the configuration file for persistent authenticated session.
- The ``--site`` and ``--cache-dir`` options were removed.
- :py:mod:`~ws.checkers.ExtlinkReplacements`: fixed tests, fixed replacement of
  Arch bug tracker links, added more replacements for Arch projects and other
  cases.
- :py:mod:`~ws.checkers.ExtlinkStatusChecker`:
  - refactored to take the URLs from the database and save the results there
  - skip links to invalid or blacklisted domains, detect sites behind
    CloudFlare protection
- :py:mod:`~ws.checkers.ExtlinkStatusUpdater`: new module which was split from
  :py:mod:`~ws.checkers.ExtlinkStatusChecker` and contains the (updated) code
  for updating the status of extlinks on wiki pages.
- :py:mod:`~ws.checkers.WikilinkChecker`: fixed urldecoding of section anchors,
  fixed race condition between the "Archive page" and "Broken section link"
  flags, removed some old and unnecessary workarounds.
- Simplified :py:class:`ws.utils.TLSAdapter` using ``ssl_version`` instead of
  ``ssl_options``.
- Many bug fixes for the :py:mod:`ws.db` module and the ``checkdb.py`` script.
- Migrated to SQLAlchemy 2.0:
  https://docs.sqlalchemy.org/en/20/changelog/migration_20.html
- The :py:mod:`ws.db` module now requires SQLAlchemy with ``asyncio`` support
  and the ``asyncpg`` driver for PostgreSQL. The synchronous interface with the
  ``psycopg2`` driver is still used as well.
- :py:mod:`ws.db.schema`: added new tables ``ws_domain`` and ``ws_url_check``
  for tracking the results of status checks for domains and URLs.

- New scripts:

  - ``delete-unused-categories.py``
  - ``localize-templates.py``
  - ``mark-archived-links.py``
  - ``race.py``
  - ``report-problems.py`` (previously ``list-problematic-pages.py``, now it
    also has an automatic report page)
  - ``update-page-language.py``

- Refactored scripts:

  - ``extlink-checker.py`` has a new required parameter ``--mode`` with two
    choices:

    1. ``check`` uses :py:mod:`~ws.checkers.ExtlinkStatusChecker` which takes
       URLs from the database and checks their status, and
    2. ``update`` uses :py:mod:`~ws.checkers.ExtlinkStatusUpdater` which takes
       the check results from the database and applies them on the wiki.

Version 1.3
-----------

`Released Jun 19, 2021 <https://github.com/lahwaacz/wiki-scripts/tree/1.3>`_
(`changes <https://github.com/lahwaacz/wiki-scripts/compare/1.2...1.3>`__)

- SQL database:
    - Implemented a subset of MediaWiki API querie. Lists: ``allpages``,
      ``alldeletedrevisions``, ``allrevisions``, ``allusers``, ``logevents``,
      ``protectedtitles``, ``recentchanges``; props: ``categories``,
      ``deletedrevisions``, ``extlinks``, ``images``, ``info``, ``iwlinks``,
      ``langlinks``, ``linkshere``, ``links``, ``pageprops``, ``redirects``,
      ``revisions``, ``sections``, ``templates``, ``transcludedin``; including
      ``generator``, ``titles`` and ``pageids`` parameters. See the GitHub
      issue for more information:
      https://github.com/lahwaacz/wiki-scripts/issues/35.
    - Implemented synchronization of revisions contents (either full or just
      the latest revision for each page).
    - Fixed many bugs in the synchronization process.
    - Implemented custom parser cache, see the GitHub issue for more
      information: https://github.com/lahwaacz/wiki-scripts/issues/42
- Removed :py:mod:`ws.cache.LatestRevisions` module. Scripts use the SQL
  database for caching.
- Merged several smaller scripts into ``list-problems.py``.
- Implemented the :py:meth:`ws.client.api.API.move` method to rename pages on
  the wiki.
- Implemented recursive template expansion using :py:mod:`mwparserfromhell` and
  the SQL database. See :py:mod:`ws.parser_helpers.template_expansion`.
- Implemented a regex-based function to check if a page is a redirect
  (:py:func:`ws.parser_helpers.wikicode.is_redirect`).
- Fixed handling of relative links and leading colons in the :py:class:`Title
  <ws.parser_helpers.title.Title>` class.
- The parameter ``--ssl-verify`` is removed, SSL certificates are always verified
  for HTTPS requests. Furthermore, TLS 1.2 or newer is required for all HTTPS
  requests.
- And much more...

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
  :py:mod:`ws.config` submodule. See `Configuration <configuration.html>`_ for
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

