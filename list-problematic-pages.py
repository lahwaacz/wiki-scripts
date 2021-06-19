#! /usr/bin/env python3

# TODO: create an on-wiki report using AutoPage

from ws.client import API
from ws.db.database import Database
from ws.parser_helpers.encodings import dotencode
import ws.ArchWiki.lang as lang

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

    for source in sorted(redirects.keys()):
        target = redirects[source]
        title = api.Title(target)

        # limit to redirects with broken fragment
        if valid_sectionname(db, title):
            continue

        print("* [[{}]] → [[{}]]".format(source, target))

def list_redirects_wrong_capitalization(api):
    # limit to redirects pointing to the main namespace, others deserve special treatment
    redirects = api.redirects.fetch(source_namespaces=[0, 4, 12], target_namespaces=[0])

    # we will count the number of uppercase letters starting each word
    def count_uppercase(text):
        words = text.split()
        firstletters = [word[0] for word in words]
        return sum(1 for c in firstletters if c.isupper())

    for source in sorted(redirects.keys()):
        target = redirects[source].split("#", maxsplit=1)[0]

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

        print("* [[{}]] → [[{}]]".format(source, target))

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

    # print talk pages of deleted pages
    for title in sorted(talks):
        _title = api.Title(title)
        if _title.articlepagename not in allpages:
            print("* [[%s]]" % title)

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

    # print talk pages associated to a redirect page
    for title in sorted(redirect_titles):
        _title = api.Title(title)
        if _title.talkpagename in talks:
            print("* [[%s]]" % _title.talkpagename)

if __name__ == "__main__":
    import ws.config

    argparser = ws.config.getArgParser(description="List redirects with broken fragments")
    API.set_argparser(argparser)
    Database.set_argparser(argparser)

    args = ws.config.parse_args()

    api = API.from_argparser(args)
    db = Database.from_argparser(args)

    print("== Redirects with broken fragments ==")
    list_redirects_broken_fragments(api, db)
    print()

    print("== Redirects with potentially wrong capitalization ==")
    print("""\
According to ArchWiki standards, the title must be sentence-case (if it is not
an acronym). We will print the wrong capitalized redirects, i.e. when
sentence-case title redirects to title-case.
""")
    list_redirects_wrong_capitalization(api)
    print()

    print("== Talk pages of deleted pages ==")
    print("The following talk pages correspond to deleted pages and should not exist.")
    list_talkpages_of_deleted_pages(api)
    print()

    print("== Talk pages of redirects ==")
    print("The following talk pages correspond to redirect pages and should be redirected as well or deleted.")
    list_talkpages_of_redirects(api)
