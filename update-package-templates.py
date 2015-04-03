#! /usr/bin/env python3

# TODO:
#   retry when edit fails
#   testing repos may contain new packages
#   is Template:Grp x86_64 only? in that case warn about i686-only groups
#   include some stats in the report
#   diff-like report showing only new issues since the last report

import argparse
import bisect
import os.path
import sys
import datetime
import json

import requests
import mwparserfromhell
import pycman
import pyalpm

from MediaWiki import API, diff_highlighted
from MediaWiki.exceptions import *
from MediaWiki.interactive import *
from ArchWiki.lang import detect_language

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
            print("Syncing AUR packages...")
            self.aurpkgs_refresh(self.aurpkgs_url)
            print("Syncing pacman database (i686)...")
            self.pacdb_refresh(self.pacdb32)
            print("Syncing pacman database (x86_64)...")
            self.pacdb_refresh(self.pacdb64)
            return True
        except requests.exceptions.RequestException:
            print("Failed to download %s" % self.aurpkgs_url, sys.stderr)
            return False
        except pyalpm.error:
            print("Failed to sync pacman database.", sys.stderr)
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


# TODO: write unit test for this function
def get_adjacent_node(wikicode, node, ignore_whitespace=False):
    """
    Get the node immediately following `node` in `wikicode`.

    :param wikicode: a :py:class:`mwparserfromhell.wikicode.Wikicode` object
    :param node: a :py:class:`mwparserfromhell.nodes.Node` object
    :param ignore_whitespace: When True, the whitespace between `node` and the
            node being returned is ignored, i.e. the returned object is
            guaranteed to not be an all white space text, but it can still be a
            text with leading space.
    :returns: a :py:class:`mwparserfromhell.nodes.Node` object or None if `node`
            is the last object in `wikicode`
    """
    i = wikicode.index(node) + 1
    try:
        n = wikicode.get(i)
        while ignore_whitespace and n.isspace():
            i += 1
            n = wikicode.get(i)
        return n
    except IndexError:
        return None

# TODO: write unit test for this function
def get_parent_wikicode(wikicode, node):
    """
    Returns the parent of `node` as a `wikicode` object.
    Raises :exc:`ValueError` if `node` is not a descendant of `wikicode`.
    """
    context, index = wikicode._do_strong_search(node, True)
    return context


class PkgUpdater:
    def __init__(self, api, aurpkgs_url, tmpdir, ssl_verify):
        self.api = api
        self.finder = PkgFinder(aurpkgs_url, tmpdir, ssl_verify)
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

    def update_package_template(self, template):
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

        param = template.get(1).value
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
        print("Parsing '%s'..." % title)
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

            hint = self.update_package_template(template)

            # add/remove/update {{Broken package link}} flag
            parent = get_parent_wikicode(wikicode, template)
            adjacent = get_adjacent_node(parent, template, ignore_whitespace=True)
            if hint is not None:
                print("warning: '{}': {}".format(template, hint))
                self.add_report_line(title, template, hint)
                broken_flag = "{{Broken package link|%s}}" % hint
                if isinstance(adjacent, mwparserfromhell.nodes.Template) and adjacent.name.matches("Broken package link"):
                    # replace since the hint might be different
                    wikicode.replace(adjacent, broken_flag)
                else:
                    wikicode.insert_after(template, broken_flag)
            else:
                if isinstance(adjacent, mwparserfromhell.nodes.Template) and adjacent.name.matches("Broken package link"):
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
                print("skipping blacklisted page '%s'" % title)
                continue
            timestamp = page["revisions"][0]["timestamp"]
            text_old = page["revisions"][0]["*"]
            text_new = self.update_page(title, text_old)
            if text_old != text_new:
                try:
#                    edit_interactive(self.api, page["pageid"], text_old, text_new, timestamp, self.edit_summary, bot="")
                    self.api.edit(page["pageid"], text_new, timestamp, self.edit_summary, bot="")
                except (APIError, APIWarnings):
                    print("error: failed to edit page '%s'" % title)

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

    def save_report(self, directory):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d")
        basename = os.path.join(directory, "update-pkgs-{}.report".format(timestamp))
        f = open(basename + ".mediawiki", "w")
        f.write(self.get_report_wikitext())
        f.close()
        print("Saved report in '%s.mediawiki'" % basename)
        f = open(basename + ".json", "w")
        json.dump(self.log, f, indent=4, sort_keys=True)
        f.close()
        print("Saved report in '%s.json'" % basename)


# any path, the dirname part must exist (e.g. path to a file that will be created in the future)
def arg_dirname_must_exist(string):
    dirname = os.path.split(string)[0]
    if not os.path.isdir(dirname):
        raise argparse.ArgumentTypeError("directory '%s' does not exist" % dirname)
    return string

# path to existing directory
def arg_existing_dir(string):
    if not os.path.isdir(string):
        raise argparse.ArgumentTypeError("directory '%s' does not exist" % string)
    return string


if __name__ == "__main__":
    argparser = argparse.ArgumentParser(description="Update Pkg/AUR templates")

    _api = argparser.add_argument_group(title="API parameters")
    _api.add_argument("--api-url", default="https://wiki.archlinux.org/api.php", metavar="URL",
            help="the URL to the wiki's api.php (default: %(default)s)")
    _api.add_argument("--cookie-path", type=arg_dirname_must_exist, default=os.path.expanduser("~/.cache/ArchWiki.bot.cookie"), metavar="PATH",
            help="path to cookie file (default: %(default)s)")
    _api.add_argument("--ssl-verify", default=1, choices=(0, 1),
            help="whether to verify SSL certificates (default: %(default)s)")

    _script = argparser.add_argument_group(title="script parameters")
    _script.add_argument("--aurpkgs-url", default="https://aur.archlinux.org/packages.gz", metavar="URL",
            help="the URL to packages.gz file on the AUR (default: %(default)s)")
    _script.add_argument("--tmp-dir", type=arg_existing_dir, default="/tmp/", metavar="PATH",
            help="temporary directory path (default: %(default)s)")
    _script.add_argument("--report-dir", type=arg_existing_dir, default=".", metavar="PATH",
            help="directory where the report should be saved")

    args = argparser.parse_args()

    # retype from int to bool
    args.ssl_verify = True if args.ssl_verify == 1 else False

    api = API(args.api_url, cookie_file=args.cookie_path, ssl_verify=args.ssl_verify)
    updater = PkgUpdater(api, args.aurpkgs_url, args.tmp_dir, args.ssl_verify)

    try:
        ret = updater.check_allpages()
        if not ret:
            sys.exit(ret)
        updater.save_report(args.report_dir)
    except KeyboardInterrupt:
        print()
        updater.save_report(args.report_dir)
        raise
