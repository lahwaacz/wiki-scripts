#! /usr/bin/env python3

# TODO:
#   retry when edit fails
#   testing repos may contain new packages
#   is Template:Grp x86_64 only? in that case warn about i686-only groups
#   include some stats in the report
#   diff-like report showing only new issues since the last report

import bisect
import os.path
import sys
import datetime
import json
import logging

import requests
import mwparserfromhell
import pycman
import pyalpm

from ws.core import API, APIError
from ws.core.lazy import LazyProperty
from ws.interactive import *
from ws.ArchWiki.lang import detect_language
from ws.parser_helpers.wikicode import get_parent_wikicode, get_adjacent_node
from ws.parser_helpers.title import canonicalize

logger = logging.getLogger(__name__)

PACCONF = """
[options]
RootDir     = /
DBPath      = {pacdbpath}
CacheDir    = {pacdbpath}
LogFile     = {pacdbpath}
# Use system GPGDir so that we don't have to populate it
GPGDir      = /etc/pacman.d/gnupg/
Architecture = {arch}

# Repos needed for Template:Pkg checking

[core]
Include = /etc/pacman.d/mirrorlist

[extra]
Include = /etc/pacman.d/mirrorlist

[community]
Include = /etc/pacman.d/mirrorlist
"""

PACCONF64_SUFFIX = """
[multilib]
Include = /etc/pacman.d/mirrorlist
"""

class PkgFinder:
    def __init__(self, aurpkgs_url, tmpdir, ssl_verify):
        self.aurpkgs_url = aurpkgs_url
        self.tmpdir = os.path.abspath(os.path.join(tmpdir, "wiki-scripts"))
        self.ssl_verify = ssl_verify

        self.aurpkgs = None
        self.pacdb32 = self.pacdb_init(PACCONF, os.path.join(self.tmpdir, "pacdbpath32"), arch="i686")
        self.pacdb64 = self.pacdb_init(PACCONF + PACCONF64_SUFFIX, os.path.join(self.tmpdir, "pacdbpath64"), arch="x86_64")
        self.aur_archived_pkgs = open("./static/aur3-archive.pkglist").read().split()

    def pacdb_init(self, config, dbpath, arch):
        os.makedirs(dbpath, exist_ok=True)
        confpath = os.path.join(dbpath, "pacman.conf")
        if not os.path.isfile(confpath):
            f = open(confpath, "w")
            f.write(config.format(pacdbpath=dbpath, arch=arch))
            f.close()
        return pycman.config.init_with_config(confpath)

    # sync database of AUR packages
    def aurpkgs_refresh(self, aurpkgs_url):
        response = requests.get(aurpkgs_url, verify=self.ssl_verify)
        response.raise_for_status()
        self.aurpkgs = sorted([line for line in response.text.splitlines() if not line.startswith("#")])

    # sync databases like pacman -Sy
    def pacdb_refresh(self, pacdb, force=False):
        for db in pacdb.get_syncdbs():
            # since this is private pacman database, there is no locking
            db.update(force)

    # sync all
    def refresh(self):
        try:
            logger.info("Syncing AUR packages...")
            self.aurpkgs_refresh(self.aurpkgs_url)
            logger.info("Syncing pacman database (i686)...")
            self.pacdb_refresh(self.pacdb32)
            logger.info("Syncing pacman database (x86_64)...")
            self.pacdb_refresh(self.pacdb64)
            return True
        except requests.exceptions.RequestException:
            logger.exception("Failed to download %s" % self.aurpkgs_url)
            return False
        except pyalpm.error:
            logger.exception("Failed to sync pacman database.")
            return False

    # try to find given package (in either 32bit or 64bit database)
    def find_pkg(self, pkgname, exact=True):
        for pacdb in (self.pacdb64, self.pacdb32):
            for db in pacdb.get_syncdbs():
                if exact is True:
                    pkg = db.get_pkg(pkgname)
                    if pkg is not None and pkg.name == pkgname:
                        return pkg
                else:
                    # iterate over all packages (db.get_pkg does only exact match)
                    for pkg in db.pkgcache:
                        # compare pkgnames in lowercase
                        if pkg.name.lower() == pkgname.lower():
                            return pkg
        return None

    # try to find given group (in either 32bit or 64bit database)
    def find_grp(self, grpname, exact=True):
        for pacdb in (self.pacdb64, self.pacdb32):
            for db in pacdb.get_syncdbs():
                if exact is True:
                    grp = db.read_grp(grpname)
                    if grp is not None and grp[0] == grpname:
                        return grp
                else:
                    # iterate over all groups (db.read_grp does only exact match)
                    for grp in db.grpcache:
                        if grp[0].lower() == grpname.lower():
                            return grp
        return None

    # check that given package exists in AUR
    def find_aur(self, pkgname):
        # all packages in AUR are strictly lowercase, but queries both via web (links) and helpers are case-insensitive
        pkgname = pkgname.lower()
        # use bisect instead of 'pkgname in self.aurpkgs' for performance
        i = bisect.bisect_left(self.aurpkgs, pkgname)
        if i != len(self.aurpkgs) and self.aurpkgs[i] == pkgname:
            return True
        return False

    # check that given package exists in AUR3 archive (aur-mirror.git)
    def find_aur3_archive(self, pkgname):
        pkgname = pkgname.lower()
        # use bisect instead of 'pkgname in self.aur_archived_pkgs' for performance
        i = bisect.bisect_left(self.aur_archived_pkgs, pkgname)
        if i != len(self.aur_archived_pkgs) and self.aur_archived_pkgs[i] == pkgname:
            return True
        return False

    # try to find a package that has given pkgname in its `replaces` array
    def find_replaces(self, pkgname, exact=True):
        for pacdb in (self.pacdb64, self.pacdb32):
            for db in pacdb.get_syncdbs():
                # iterate over all packages (search like pacman -Ss is not enough when
                # the pkgname is not proper keyword)
                for pkg in db.pkgcache:
                    if exact is True and pkgname in pkg.replaces:
                        return pkg
                    elif exact is False and pkgname.lower() in (_pkgname.lower() for _pkgname in pkg.replaces):
                        return pkg
        return None


class PkgUpdater:
    def __init__(self, api, aurpkgs_url, tmpdir, ssl_verify, report_dir):
        self.api = api
        self.finder = PkgFinder(aurpkgs_url, tmpdir, ssl_verify)
        self.report_dir = report_dir

        self.edit_summary = "update Pkg/AUR templates (https://github.com/lahwaacz/wiki-scripts/blob/master/update-package-templates.py)"

        # log data for easy report generation
        # the dictionary looks like this:
        # {"English": {"Page title": [_list item_, ...], ...}, ...}
        # where _list item_ is the text representing the warning/error + hints (formatted
        # with wiki markup)
        self.log = {}

        # titles of pages that should not be processed
        self.blacklist_pages = [
            "AUR Cleanup Day/2010",
            "Christmas Cleanup/2011",
            "Midyear Cleanup/2013",
            "Security Advisories",
            "CVE",
        ]

    @staticmethod
    def set_argparser(argparser):
        # first try to set options for objects we depend on
        present_groups = [group.title for group in argparser._action_groups]
        if "Connection parameters" not in present_groups:
            API.set_argparser(argparser)

        group = argparser.add_argument_group(title="script parameters")
        group.add_argument("--aurpkgs-url", default="https://aur.archlinux.org/packages.gz", metavar="URL",
                help="the URL to packages.gz file on the AUR (default: %(default)s)")
        group.add_argument("--report-dir", type=ws.config.argtype_existing_dir, default=".", metavar="PATH",
                help="directory where the report should be saved")

    @classmethod
    def from_argparser(klass, args, api=None):
        if api is None:
            api = API.from_argparser(args)
        return klass(api, args.aurpkgs_url, args.tmp_dir, args.ssl_verify, args.report_dir)

    @LazyProperty
    def _templates_list(self):
        result = self.api.generator(generator="allpages", gapnamespace=10, gaplimit="max", gapfilterredir="nonredirects")
        return [page["title"].split(":", maxsplit=1)[1] for page in result]

    def _localized_template(self, template, lang="English"):
        assert(canonicalize(template) in self._templates_list)
        localized = "{} ({})".format(template, lang) if lang != "English" else template
        if canonicalize(localized) in self._templates_list:
            return localized
        # fall back to English
        return template

    def update_package_template(self, template, lang="English"):
        """
        Update given package template.

        :param template: A :py:class:`mwparserfromhell.nodes.Template` object; it is assumed
                         that `template.name` matches either `Aur`, `AUR`, `Grp` or `Pkg`.
        :returns: A _hint_, which is either `None` if the template was updated succesfully,
                  or a string uniquely identifying the problem (parseable as wikicode).
        """
        hint = None
        newtemplate = None

        # AUR, Grp, Pkg templates all take exactly 1 parameter
        if len(template.params) != 1:
            hint = "invalid number of template parameters"

        try:
            param = template.get(1).value
        except ValueError:
            raise TemplateParametersError(template)

        # strip whitespace for searching (spacing is preserved on the wiki)
        pkgname = param.strip()

        if self.finder.find_pkg(pkgname):
            newtemplate = "Pkg"
        elif self.finder.find_aur(pkgname):
            newtemplate = "AUR"
        elif self.finder.find_grp(pkgname):
            newtemplate = "Grp"

        if newtemplate is not None:
            # update template name (avoid changing capitalization and spacing)
            if template.name.lower().strip() != newtemplate.lower():
                template.name = newtemplate
            return hint  # either None or "invalid number of template parameters"

        # try to find package with different capitalization
        # (safe to update automatically, uppercase letters in pkgnames are very rare,
        # two pkgnames differing only in capitalization are even rarer)
        pkg_loose = self.finder.find_pkg(pkgname, exact=False)
        if pkg_loose:
            template.name = "Pkg"
            template.add(1, pkg_loose.name, preserve_spacing=False)
            return None

        grp_loose = self.finder.find_grp(pkgname, exact=False)
        if grp_loose:
            template.name = "Grp"
            template.add(1, grp_loose[0], preserve_spacing=False)
            return None

        # package not found, select appropriate hint
        replacedby = self.finder.find_replaces(pkgname, exact=False)
        if replacedby:
            return "replaced by {{Pkg|%s}}" % replacedby.name

        # check AUR3 archive (aur-mirror.git)
        if self.finder.find_aur3_archive(pkgname):
            return "{{%s|%s}}" % (self._localized_template("aur-mirror", lang), pkgname.lower())

        return "package not found"

    def update_page(self, title, text):
        """
        Update package templates on given page.

        Parse wikitext, try to update all package templates, handle broken package links:
            - print warning to console
            - append message to self.log
            - mark it with {{Broken package link}} in the wikicode

        :param title: title of the wiki page
        :param text: content of the wiki page
        :returns: a :py:class:`mwparserfromhell.wikicode.Wikicode` object with the updated
                  content of the page
        """
        logger.info("Parsing '%s'..." % title)
        lang = detect_language(title)[1]
        wikicode = mwparserfromhell.parse(text)
        for template in wikicode.ifilter_templates():
            # skip unrelated templates
            if not any(template.name.matches(tmp) for tmp in ["Aur", "AUR", "Grp", "Pkg"]):
                continue

            # skip templates no longer under wikicode (templates nested under previously
            # removed parent template are still detected by ifilter)
            try:
                wikicode.index(template, True)
            except ValueError:
                continue

            hint = self.update_package_template(template, lang)

            # add/remove/update {{Broken package link}} flag
            parent = get_parent_wikicode(wikicode, template)
            adjacent = get_adjacent_node(parent, template, ignore_whitespace=True)
            if hint is not None:
                logger.warning("broken package link: {}: {}".format(template, hint))
                self.add_report_line(title, template, hint)
                broken_flag = "{{%s|%s}}" % (self._localized_template("Broken package link", lang), hint)
                if isinstance(adjacent, mwparserfromhell.nodes.Template) and canonicalize(adjacent.name).startswith("Broken package link"):
                    # replace since the hint might be different
                    wikicode.replace(adjacent, broken_flag)
                else:
                    wikicode.insert_after(template, broken_flag)
            else:
                if isinstance(adjacent, mwparserfromhell.nodes.Template) and canonicalize(adjacent.name).startswith("Broken package link"):
                    # package has been found again, remove existing flag
                    wikicode.remove(adjacent)

        return wikicode

    def check_allpages(self):
        if not self.finder.refresh():
            return False

        # ensure that we are authenticated
        require_login(self.api)

        for page in self.api.generator(generator="allpages", gaplimit="100", gapfilterredir="nonredirects", prop="revisions", rvprop="content|timestamp"):
            title = page["title"]
            if title in self.blacklist_pages:
                logger.info("skipping blacklisted page '%s'" % title)
                continue
            timestamp = page["revisions"][0]["timestamp"]
            text_old = page["revisions"][0]["*"]
            text_new = self.update_page(title, text_old)
            if text_old != text_new:
                try:
#                    edit_interactive(self.api, title, page["pageid"], text_old, text_new, timestamp, self.edit_summary, bot="")
                    self.api.edit(title, page["pageid"], text_new, timestamp, self.edit_summary, bot="")
                except APIError:
                    pass

        return True

    def add_report_line(self, title, template, message):
        message = "<nowiki>{}</nowiki> ({})".format(template, message)
        lang = detect_language(title)[1]
        if lang not in self.log:
            self.log[lang] = {}
        if title in self.log[lang]:
            self.log[lang][title].append(message)
        else:
            self.log[lang][title] = [message]

    def get_report_wikitext(self):
        report = ""
        for lang in sorted(self.log.keys()):
            report += "\n== %s ==\n\n" % lang
            pages = self.log[lang]
            for title in sorted(pages.keys()):
                report += "* [[%s]]\n" % title
                for message in pages[title]:
                    report += "** %s\n" % message
        return report

    def save_report(self):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d")
        basename = os.path.join(self.report_dir, "update-pkgs-{}.report".format(timestamp))
        f = open(basename + ".mediawiki", "w")
        f.write(self.get_report_wikitext())
        f.close()
        logger.info("Saved report in '%s.mediawiki'" % basename)
        f = open(basename + ".json", "w")
        json.dump(self.log, f, indent=4, sort_keys=True)
        f.close()
        logger.info("Saved report in '%s.json'" % basename)


class TemplateParametersError(Exception):
    """ Raised when parsing a template parameter failed.
    """
    def __init__(self, template):
        self.message = "Failed to parse a template parameter. This likely indicates a " \
                       "syntax error on the page.\n\n" \
                       "Template text: '{}'\n\n" \
                       "Parsed parameters: {}".format(template, template.params)

    def __str__(self):
        return self.message


if __name__ == "__main__":
    import ws.config

    updater = ws.config.object_from_argparser(PkgUpdater, description="Update Pkg/AUR templates")

    try:
        ret = updater.check_allpages()
        if not ret:
            sys.exit(ret)
        updater.save_report()
    except KeyboardInterrupt:
        print()
        updater.save_report()
        raise
