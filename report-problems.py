#! /usr/bin/env python3

import datetime
import logging

from ws.client import API
from ws.db.database import Database
from ws.parser_helpers.encodings import dotencode
import ws.ArchWiki.lang as lang
from ws.autopage import AutoPage
from ws.interactive import require_login

logger = logging.getLogger(__name__)

def valid_sectionname(db, title):
    """
    Checks if the ``sectionname`` property of given title is valid, i.e. if a
    corresponding section exists on a page with given title.

    .. note::
        Validation is limited to pages in the Main namespace for easier access
        to the cache; anchors on other pages are considered to be always valid.

    :param ws.db.database.Database db: database object
    :param title: parsed title of the wikilink to be checked
    :type title: ws.parser_helpers.title.Title
    :returns: ``True`` if the anchor corresponds to an existing section
    """
    # we can't check interwiki links
    if title.iwprefix:
        return True

    # empty sectionname is always valid
    if title.sectionname == "":
        return True

    # get list of valid anchors
    result = db.query(titles=title.fullpagename, prop="sections", secprop={"anchor"})
    page = next(result)
    anchors = [section["anchor"] for section in page.get("sections", [])]

    # encode the given anchor and validate
    return dotencode(title.sectionname) in anchors

def list_redirects_broken_fragments(api, db):
    db.sync_with_api(api)
    db.sync_revisions_content(api, mode="latest")
    db.update_parser_cache()

    # limit to redirects pointing to the content namespaces
    redirects = api.redirects.fetch(target_namespaces=[0, 4, 12])

    report = ""
    for source, target in redirects.items():
        title = api.Title(target)

        # limit to redirects with broken fragment
        if valid_sectionname(db, title):
            continue

        report += f"* [[{source}]] → [[{target}]]\n"

    return report

def list_redirects_wrong_capitalization(api):
    # limit to redirects pointing to the main namespace, others deserve special treatment
    redirects = api.redirects.fetch(source_namespaces=[0, 4, 12], target_namespaces=[0])

    # we will count the number of uppercase letters starting each word
    def count_uppercase(text):
        words = text.split()
        firstletters = [word[0] for word in words]
        return sum(1 for c in firstletters if c.isupper())

    report = ""
    for source, target in redirects.items():
        target = target.split("#", maxsplit=1)[0]

        # limit to redirects whose source and target title differ only in capitalization
        if source.lower() != target.lower():
            continue

        # limit to multiple-word titles
        pure, _ = lang.detect_language(source)
        if len(pure.split()) == 1:
            continue

        # limit to sentence-case titles redirecting to title-case
        if count_uppercase(source) >= count_uppercase(target):
            continue

        report += f"* [[{source}]] → [[{target}]]\n"

    return report

def list_redirects_different_namespace(api):
    # limit to redirects from content namespaces
    redirects = api.redirects.fetch(source_namespaces=[0, 4, 12, 14, 3000])

    report = ""
    for source, target in redirects.items():
        title = api.Title(target)
        if title.namespacenumber not in {0, 4, 12, 14, 3000}:
            report += f"* [[{source}]] → [[{target}]]\n"

    return report

def list_talkpages_of_deleted_pages(api):
    # get titles of all pages in 'Main', 'ArchWiki' and 'Help' namespaces
    allpages = []
    for ns in ["0", "4", "12"]:
        _pages = api.generator(generator="allpages", gaplimit="max", gapnamespace=ns)
        allpages.extend([page["title"] for page in _pages])

    # get titles of all redirect pages in 'Talk', 'ArchWiki talk' and 'Help talk' namespaces
    talks = []
    for ns in ["1", "5", "13"]:
        pages = api.generator(generator="allpages", gaplimit="max", gapnamespace=ns)
        talks.extend([page["title"] for page in pages])

    # report talk pages of deleted pages
    report = ""
    for title in talks:
        _title = api.Title(title)
        if _title.articlepagename not in allpages:
            report += f"* [[{title}]]\n"

    return report

def list_talkpages_of_redirects(api):
    # get titles of all redirect pages in 'Main', 'ArchWiki' and 'Help' namespaces
    redirect_titles = []
    for ns in ["0", "4", "12"]:
        _pages = api.generator(generator="allpages", gaplimit="max", gapfilterredir="redirects", gapnamespace=ns)
        redirect_titles.extend([page["title"] for page in _pages])

    # get titles of all pages in 'Talk', 'ArchWiki talk' and 'Help talk' namespaces
    talks = []
    for ns in ["1", "5", "13"]:
        # limiting to talk pages that are not redirects is also useful
    #    pages = api.generator(generator="allpages", gaplimit="max", gapnamespace=ns)
        pages = api.generator(generator="allpages", gaplimit="max", gapfilterredir="nonredirects", gapnamespace=ns)
        talks.extend([page["title"] for page in pages])

    # report talk pages associated to a redirect page
    report = ""
    for title in redirect_titles:
        _title = api.Title(title)
        if _title.talkpagename in talks:
            report += f"* [[{_title.talkpagename}]]\n"

    return report

def list_mismatched_talkpage_redirects(api):
    report = ""
    redirects = api.redirects.map
    for source, target in redirects.items():
        source_title = api.Title(source)
        target_title = api.Title(target)
        # process only talk pages
        if source_title.talkpagename != source:
            continue

        article = source_title.articlepagename
        article_target = redirects.get(article)
        target_article = target_title.articlepagename

        # skip if the article redirects to the same talk page as the source itself
        # (this covers the [[Requests]] → [[ArchWiki talk:Requests]] etc. redirects)
        if article_target == target and target_title.talkpagename == target:
            continue
        # skip false positives: talk pages of the List of applications' subpages
        # redirect to Talk:List of applications
        if target == "Talk:List of applications":
            if article.startswith("List of applications/"):
                continue
            if article_target is not None and article_target.startswith("List of applications/"):
                continue

        if article_target is None:
            # do not report archived talk pages
            if target != "ArchWiki:Archive":
                report += f"* [[{source}]] ([[:{article}]] is not a redirect)\n"
        # use .fullpagename to drop the section name from the article target
        elif api.Title(article_target).fullpagename != target_article:
            report += f"* [[{source}]] → [[{target}]] (article redirects to [[:{article_target}]], but the target's article is [[:{target_article}]])\n"

    return report

def sortlines(text):
    lines = text.strip("\n").splitlines()
    lines.sort()
    return "\n".join(lines)

def make_report(api, db):

    result_redirects_broken_fragments = sortlines(list_redirects_broken_fragments(api, db))
    result_redirects_wrong_capitalization = sortlines(list_redirects_wrong_capitalization(api))
    result_redirects_different_namespace = sortlines(list_redirects_different_namespace(api))
    result_talkpages_of_deleted_pages = sortlines(list_talkpages_of_deleted_pages(api))
    result_talkpages_of_redirects = sortlines(list_talkpages_of_redirects(api))
    result_mismatched_talkpage_redirects = sortlines(list_mismatched_talkpage_redirects(api))

    report = f"""
== Redirects with broken fragments ==

{result_redirects_broken_fragments}

== Redirects with potentially wrong capitalization ==

According to ArchWiki standards, the title must be sentence-case (if it is not
an acronym). We will print the wrong capitalized redirects, i.e. when
sentence-case title redirects to title-case.

{result_redirects_wrong_capitalization}

== Redirects to a different namespace ==

These pages from the main, ''ArchWiki:'', ''Help:'', ''Category:'' and
''DeveloperWiki:'' namespaces redirect to a namespace different than these 5
namespaces.

{result_redirects_different_namespace}

== Talk pages of deleted pages ==

The following talk pages correspond to deleted pages and should not exist.

{result_talkpages_of_deleted_pages}

== Talk pages of redirects ==

The following talk pages correspond to redirect pages and should be redirected as well or deleted.

{result_talkpages_of_redirects}

== Talk pages of redirects pointing to a different page ==

The following talk pages correspond to redirect pages, but they point to a different page.
I.e, pages such that if A redirects to B, Talk:A redirects to Talk:C rather than Talk:B.

{result_mismatched_talkpage_redirects}
"""
    return report

def save_report(api, report_page, contents):
    page = AutoPage(api, report_page)
    div = page.get_tag_by_id("div", "wiki-scripts-problems-report")
    if not page.is_old_enough(datetime.timedelta(days=0), strip_time=True):
        logger.info("The report page on the wiki has already been updated in the past 7 days, skipping today's update.")
        return

    div.contents = contents
    page.save("automatic update", False)
    logger.info("Saved report to the [[{}]] page on the wiki.".format(report_page))

if __name__ == "__main__":
    import ws.config

    argparser = ws.config.getArgParser(description="List redirects with broken fragments")
    API.set_argparser(argparser)
    Database.set_argparser(argparser)

    group = argparser.add_argument_group(title="script parameters")
    group.add_argument("--report-page", type=str, default=None, metavar="PAGENAME",
            help="existing report page on the wiki (default: %(default)s)")

    args = ws.config.parse_args(argparser)

    api = API.from_argparser(args)
    db = Database.from_argparser(args)

    # ensure that we are authenticated
    require_login(api)

    report = make_report(api, db)
    if args.report_page:
        save_report(api, args.report_page, report)
    else:
        print(report)
