wiki-scripts documentation
==========================

*wiki-scripts* is a collection of scripts automating common maintenance tasks on
`ArchWiki`_. The underlying :py:mod:`ws` module is general and reusable on any
wiki powered by `MediaWiki`_.

.. _ArchWiki: https://wiki.archlinux.org
.. _MediaWiki: https://www.mediawiki.org/wiki/MediaWiki

.. the "Featured scripts" section
.. include:: ../README.rst
    :start-after: featured-scripts-section-start
    :end-before: featured-scripts-section-end

.. the "Installation" section
.. include:: ../README.rst
    :start-after: install-section-start
    :end-before: install-section-end

Acknowledgement
---------------

There is a `list of client software`_ maintained on mediawiki.org, many of them
are quite inspirational.

- `simplemediawiki`_ is the original inspiration for the core
  :py:mod:`ws.core.connection` and (partially) :py:mod:`ws.core.api` modules.
- Some scripts are inspired by the `Wiki Monkey`_'s plugins, but (obviously) were
  written from scratch.

.. _list of client software: https://www.mediawiki.org/wiki/API:Client_code#Python
.. _simplemediawiki: https://github.com/ianweller/python-simplemediawiki
.. _Wiki Monkey: https://github.com/kynikos/wiki-monkey

Site map
--------

.. toctree::
    :maxdepth: 4

    configuration
    tutorial
    changelog
    modules

Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
