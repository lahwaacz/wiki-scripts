#! /usr/bin/env python3

# TODO:
#   the log should be just a JSON file containing all necessary information, this way it is possible to avoid log parsing completely
#   retry when edit fails
#   testing repos may contain new packages
#   is Template:Grp x86_64 only? in that case warn about i686-only groups

import bisect
import os.path
import sys
import time
import requests
import mwparserfromhell
import pycman
import pyalpm

from MediaWiki import API, diff_highlighted
from MediaWiki.exceptions import *
from MediaWiki.interactive import *

pacconf = """
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

pacconf64_suffix = """
[multilib]
Include = /etc/pacman.d/mirrorlist
"""

class PkgUpdater:
    def __init__(self, api_url, cookie_path, aurpkgs_url, tmpdir, ssl_verify=True):
        self.api = API(api_url, cookie_file=cookie_path, ssl_verify=ssl_verify)
        self.aurpkgs_url = aurpkgs_url
        self.tmpdir = tmpdir
        self.ssl_verify = ssl_verify

        self.aurpkgs = None
        self.pacdb32 = None
        self.pacdb64 = None
        
        self.edit_summary = "update Pkg/AUR templates (testing https://github.com/lahwaacz/wiki-scripts/blob/master/update-package-templates.py)"

    def aurpkgs_init(self, aurpkgs_url):
        r = requests.get(aurpkgs_url, verify=self.ssl_verify)
        r.raise_for_status()
        self.aurpkgs = sorted([line for line in r.text.splitlines() if not line.startswith("#")])

    def pacdb_init(self, config, dbpath, arch):
        if not os.path.isdir(dbpath):
            os.makedirs(dbpath)
        confpath = os.path.join(dbpath, "pacman.conf")
        if not os.path.isfile(confpath):
            f = open(confpath, "w")
            f.write(config.format(pacdbpath=dbpath, arch=arch))
            f.close()
        return pycman.config.init_with_config(confpath)

    # Sync databases like pacman -Sy
    def pacdb_refresh(self, pacdb, force=False):
        for db in pacdb.get_syncdbs():
            # since this is private pacman database, there is no locking
            db.update(force)

    # check that given package exists in given database
    # like `pacman -Ss`, but exact match only
    def pacdb_find_pkg(self, pacdb, pkgname):
        for db in pacdb.get_syncdbs():
            pkg = db.get_pkg(pkgname)
            if pkg is not None and pkg.name == pkgname:
                return True
        return False

    # check that given group exists in given database
    def pacdb_find_grp(self, pacdb, grpname):
        for db in pacdb.get_syncdbs():
            grp = db.read_grp(grpname)
            if grp is not None and grp[0] == grpname:
                return True
        return False

    # check if given package exists as either 32bit or 64bit package
    def find_pkg(self, pkgname):
        return self.pacdb_find_pkg(self.pacdb64, pkgname) or self.pacdb_find_pkg(self.pacdb32, pkgname)

    # check if given group exists as either 32bit or 64bit package group
    def find_grp(self, grpname):
        return self.pacdb_find_grp(self.pacdb64, grpname) or self.pacdb_find_grp(self.pacdb32, grpname)

    # check that given package exists in AUR
    def find_AUR(self, pkgname):
        # use bisect instead of 'pkgname in self.aurpkgs' for performance
        i = bisect.bisect_left(self.aurpkgs, pkgname)
        if i != len(self.aurpkgs) and self.aurpkgs[i] == pkgname:
            return True
        return False

    # parse wikitext, try to update all package templates, print warnings
    # returns updated wikitext
    def update_page(self, title, text):
        print("Parsing '%s'..." % title)
        wikicode = mwparserfromhell.parse(text)
        for template in wikicode.filter_templates():
            # skip unrelated templates
            if not any(template.name.matches(tmp) for tmp in ["Aur", "AUR", "Grp", "Pkg"]):
                continue

            # AUR, Grp, Pkg templates all take exactly 1 parameter
            if len(template.params) != 1:
                print("warning: template '%s' takes exactly 1 parameter, got %s" % (template.name, template))

            param = template.get(1).value
            # TODO: warn about uppercase
            # TODO: force the param to be lowercase + whitespace-stripped?
            param = param.lower().strip()
            if template.name.matches("Pkg") and not self.find_pkg(param):
                if self.find_AUR(param):
                    template.name = "AUR"
                elif self.find_grp(param):
                    template.name = "Grp"
                else:
                    print("warning: package '%s' does not exist neither in official repositories nor in AUR nor as package group" % param)
            elif template.name.matches("Grp") and not self.find_grp(param):
                if self.find_pkg(param):
                    template.name = "Pkg"
                elif self.find_AUR(param):
                    template.name = "AUR"
                else:
                    print("warning: package '%s' does not exist neither in official repositories nor in the AUR nor as package group" % param)
            elif (template.name.matches("Aur") or template.name.matches("AUR")) and not self.find_AUR(param):
                if self.find_pkg(param):
                    template.name = "Pkg"
                elif self.find_grp(param):
                    template.name = "Grp"
                else:
                    print("warning: package '%s' does not exist neither in official repositories nor in the AUR nor as package group" % param)

        return wikicode

    def check_allpages(self):
        self.aurpkgs_init(self.aurpkgs_url)
        try:
            self.aurpkgs_init(self.aurpkgs_url)
        except requests.exceptions.RequestException:
            print("Failed to download %s" % self.aurpkgs_url)
            return False

        self.pacdb32 = self.pacdb_init(pacconf, os.path.join(self.tmpdir, "pacdbpath32"), arch="i686")
        self.pacdb64 = self.pacdb_init(pacconf + pacconf64_suffix, os.path.join(self.tmpdir, "pacdbpath64"), arch="x86_64")

        try:
            print("Syncing pacman database (i686)...")
            self.pacdb_refresh(self.pacdb32)
            print("Syncing pacman database (x86_64)...")
            self.pacdb_refresh(self.pacdb64)
        except pyalpm.error:
            print("Failed to sync pacman database.")
            return False
        
        # ensure that we are authenticated
        require_login(self.api)

        for page in self.api.generator(generator="allpages", gaplimit="100", gapfilterredir="nonredirects", prop="revisions", rvprop="content|timestamp"):
            title = page["title"]
            timestamp = page["revisions"][0]["timestamp"]
            text_old = page["revisions"][0]["*"]
            text_new = self.update_page(title, text_old)
            if text_old != text_new:
                try:
#                    edit_interactive(self.api, page["pageid"], text_old, text_new, timestamp, self.edit_summary, bot="")
                    self.api.edit(page["pageid"], text_new, timestamp, self.edit_summary, bot="")
                    print("Edit to page '%s' succesful, sleeping for 1 second..." % title)
                    time.sleep(1)
                except (APIError, APIWarning):
                    print("error: failed to edit page '%s'" % title)

        return True


if __name__ == "__main__":
    # TODO: take command line arguments
    api_url = "https://wiki.archlinux.org/api.php"
    cookie_path = os.path.expanduser("~/.cache/ArchWiki.bot.cookie")
#    api_url = "https://localhost/mediawiki/api.php"
#    cookie_path = os.path.expanduser("~/.cache/LocalArchWiki.bot.cookie")
    aurpkgs_url = "https://aur.archlinux.org/packages.gz"
    tmpdir = "/tmp/wiki-scripts/"

    updater = PkgUpdater(api_url, cookie_path, aurpkgs_url, tmpdir)
    sys.exit(not updater.check_allpages())
