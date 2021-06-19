#! /usr/bin/env python3

from ws.client import API
from ws.interactive import require_login
import ws.config

api = ws.config.object_from_argparser(API, description="Migration of the DeveloperWiki pages")
require_login(api)

if "DeveloperWiki" in api.site.namespacenames:
    stage = 2
else:
    stage = 1
print("Stage of the migration: {}".format(stage))

# temporary prefix to be used during the migration
tmp_prefix = "Tmp:"

# list of all DeveloperWiki pages which were deleted before the migration
# (they could be identified automatically before stage 1, but have to be
# hardcoded for stage 2)
deleted_pages = [
    "DeveloperWiki:DevopsMeetings/2019-01-02",
    "DeveloperWiki:DevopsMeetings/2019-10-9",
    "DeveloperWiki:Policies",
]

if stage == 1:
    # collect all existing pages starting with "DeveloperWiki:" or "DeveloperWiki_talk:" or "Talk:DeveloperWiki:"
    pages = []
    talkpages = []
    for page in api.generator(generator="allpages", gaplimit="max"):
        if page["title"].startswith("DeveloperWiki:"):
            pages.append(page["title"])
        if page["title"].startswith("DeveloperWiki talk:"):
            pages.append(page["title"])
    for page in api.generator(generator="allpages", gaplimit="max", gapnamespace=1):
        if page["title"].startswith("Talk:DeveloperWiki:"):
            pages.append(page["title"])

    # undelete all deleted pages and add them to the list
    for page in deleted_pages:
        # (skip pages which were already undeleted - testing only...)
        if page in pages:
            continue
        api.call_with_csrftoken(action="undelete",
                                title=page,
                                reason="temporarily undeleting due to The Big Migration of DeveloperWiki Pages; see [[ArchWiki talk:Maintenance Team#Namespace for developers' pages]] for details",
                                tags="wiki-scripts")
        pages.append(page)

    # move (without redirect) all selected pages to a temporary prefix
    for page in pages:
        api.move(page,
                 tmp_prefix + page,
                 reason="temporarily moving to a temporary prefix due to The Big Migration of DeveloperWiki Pages; see [[ArchWiki talk:Maintenance Team#Namespace for developers' pages]] for details",
                 movetalk=False,
                 movesubpages=False,
                 noredirect=True)

elif stage == 2:
    # collect all DeveloperWiki pages and talk pages
    pages = []
    for page in api.generator(generator="allpages", gaplimit="max"):
        if page["title"].startswith(tmp_prefix + "DeveloperWiki:"):
            pages.append(page["title"])
        if page["title"].startswith(tmp_prefix + "DeveloperWiki talk:"):
            pages.append(page["title"])
        if page["title"].startswith(tmp_prefix + "Talk:DeveloperWiki:"):
            pages.append(page["title"])

    for page in pages:
        # unprotect the page (the whole "DeveloperWiki:" namespace will be protected)
        api.call_with_csrftoken(action="protect",
                                title=page,
                                protections="edit=all|move=all",
                                reason="dropping page-level protections before moving into the DeveloperWiki: namespace which will be protected by default; see [[ArchWiki talk:Maintenance Team#Namespace for developers' pages]] for details",
                                tags="wiki-scripts")
        # move (without redirect) the DeveloperWiki pages into the "DeveloperWiki:" or "DeveloperWiki talk:" namespace
        newtitle = page.replace(tmp_prefix, "", 1)
        if newtitle.startswith("Talk:DeveloperWiki:"):
            newtitle = newtitle.replace("Talk:DeveloperWiki:", "DeveloperWiki talk:", 1)
        api.move(page,
                 newtitle,
                 reason="The Big Migration of DeveloperWiki Pages is finished, moving into the DeveloperWiki namespace; see [[ArchWiki talk:Maintenance Team#Namespace for developers' pages]] for details",
                 movetalk=False,
                 movesubpages=False,
                 noredirect=True)

    # redelete the previously deleted pages
    for page in deleted_pages:
        api.call_with_csrftoken(action="delete",
                                title=page,
                                reason="delete previously deleted page after the migration of DeveloperWiki pages; see [[ArchWiki talk:Maintenance Team#Namespace for developers' pages]] for details",
                                tags="wiki-scripts")
