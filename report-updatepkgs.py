#! /usr/bin/env

# CHANGELOG:
#   v0.1    https://gist.github.com/lahwaacz/10307189/ed8cc4b7042e10ceb407fd7554e1e112c4de967b
#           basic version parsing Wiki Monkey's logs using regular expressions
#   v0.2    https://gist.github.com/lahwaacz/10307189/781f458f63f2831fac1f9945df90912c217908be
#           grouping by page language, parsing JSON data instead of regular expression matches

# TODO:
#   group by language
#       interface to ArchWiki module to parse language from title
#   log JSON data in the main script
#   group by package instead?

import sys
import re

from ArchWiki.lang import detect_language

class PackageTemplatesFilter:
    def __init__(self):
        self.pages = {}

    def add_log(self, logfile):
        lines = open(logfile, "r").readlines()
        title = ""
        lang = ""
        for line in lines:
            # update current page title
            m = re.match(r"Parsing\ '(?P<title>[^{}]+)'\.\.\.", line)
            if m:
                title = m.groupdict()["title"]
                lang = detect_language(title)[1]

            # detect warnings for packages not found in any repo
            m = re.match(r"warning:\ package\ '(?P<pkg>[a-zA-Z0-9@._+-]+)' does not exist.*", line)
            if m:
                pkg = m.groupdict()["pkg"]
                if lang not in self.pages:
                    self.pages[lang] = {} 
                if title in self.pages[lang]:
                    self.pages[lang][title].append(pkg)
                else:
                    self.pages[lang][title] = [pkg]

    def report(self):
        report = ""
        for lang in sorted(self.pages.keys()):
            report += "== %s ==\n" % lang
            pages = self.pages[lang]
            for title in sorted(pages.keys()):
                report += "* [[%s]]\n" % title
                for pkg in pages[title]:
                    report += "** %s\n" % pkg
        return report 


if __name__ == "__main__":
    f = PackageTemplatesFilter()
    for log in sys.argv[1:]:
        f.add_log(log)

    print(f.report())

#    import itertools
#    pkgs = f.pages.values()
#    print("pages: %d" % len(f.pages.keys()))
#    print("pkgs: %d" % len(list(itertools.chain(*pkgs))))
#    print("unique: %d" % len(set(itertools.chain(*pkgs))))
