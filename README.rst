wiki-scripts
============

Collection of scripts automating common maintenance tasks on `ArchWiki`_.
The underlying ``ws`` module is general and reusable on any wiki powered by
`MediaWiki`_.

.. _ArchWiki: https://wiki.archlinux.org
.. _MediaWiki: https://www.mediawiki.org/wiki/MediaWiki

.. featured-scripts-section-start

Featured scripts
----------------

- ``link-checker.py``
  parses all pages on the wiki and tries to fix broken wikilinks, simplify
  links over redirects and relative links, and to beautify them based on
  ArchWiki's `style recommendations`_.
- ``statistics.py``
  generates automatic updates to the `ArchWiki:Statistics`_ page.
- ``update-interlanguage-links.py``
  updates the interlanguage links based on the ArchWiki's `interlanguage map`_.
- ``update-package-templates.py``
  finds broken links using the `AUR`_/`Grp`_/`Pkg`_ templates and tries to
  update them (for example when a package has been moved from the AUR to the
  official repositories).

For a full list of available scripts see the root directory of the
`git repository`_.

.. _`style recommendations`: https://wiki.archlinux.org/index.php/Help:Style
.. _`ArchWiki:Statistics`: https://wiki.archlinux.org/index.php/ArchWiki:Statistics
.. _`interlanguage map`: https://wiki.archlinux.org/index.php/Help:I18n
.. _`AUR`: https://wiki.archlinux.org/index.php/Template:AUR
.. _`Grp`: https://wiki.archlinux.org/index.php/Template:Grp
.. _`Pkg`: https://wiki.archlinux.org/index.php/Template:Pkg
.. _`git repository`: https://github.com/lahwaacz/wiki-scripts

.. featured-scripts-section-end

.. install-section-start

Installation
------------

Get the latest development version by cloning the git repository:

.. code::

    git clone git@github.com:lahwaacz/wiki-scripts.git
    cd wiki-scripts

Alternatively download a tarball of the `latest stable release`_.

There is no package on PyPI or any other repository yet, all dependencies have
to be installed manually.

.. _latest stable release: https://github.com/lahwaacz/wiki-scripts/releases/latest

Requirements
............

- `Python`_ version 3
- `Requests`_
- `mwparserfromhell`_
- `ConfigArgParse`_ (modified, bundled as git submodule)
- `configfile`_

.. _Python: https://www.python.org/
.. _Requests: http://python-requests.org
.. _mwparserfromhell: https://github.com/earwig/mwparserfromhell
.. _ConfigArgParse: https://github.com/lahwaacz/ConfigArgParse/tree/config_files_without_merging
.. _configfile: https://github.com/kynikos/lib.py.configfile

The following are required only by some scripts:

- `WikEdDiff`_ (for highlighting differences between revisions in interactive mode)
- `Pygments`_ (alternative highlighter when WikEdDiff is not available)
- `pyalpm`_ (for ``update-package-templates.py``)
- `NumPy`_ and `matplotlib`_ (for ``statistics_histograms.py``)

.. _WikEdDiff: https://github.com/lahwaacz/python-wikeddiff
.. _Pygments: http://pygments.org/
.. _pyalpm: https://projects.archlinux.org/users/remy/pyalpm.git/
.. _NumPy: http://www.numpy.org/
.. _matplotlib: http://matplotlib.org/

Optional dependencies:

- `Tk/Tcl`_ (for copying the output of ``statistics.py`` to the clipboard)
- `colorlog`_ (for colorized logging output)

.. _Tk/Tcl: https://docs.python.org/3.4/library/tk.html
.. _colorlog: https://github.com/borntyping/python-colorlog

Tools used for development:

- `nose`_
- `nosecover3`_
- `flake8`_
- `sphinx`_
- `fabric`_

.. _nose: https://github.com/nose-devs/nose
.. _nosecover3: https://github.com/ask/nosecover3
.. _flake8: https://pypi.python.org/pypi/flake8
.. _sphinx: http://sphinx-doc.org/
.. _fabric: http://www.fabfile.org/

.. install-section-end

Documentation
-------------

Please see the `full documentation <http://lahwaacz.github.io/wiki-scripts/>`_
for more information.
