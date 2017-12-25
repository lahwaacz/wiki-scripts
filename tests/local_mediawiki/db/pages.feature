# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Syncing the page tables

    Background:
        Given an api to an empty MediaWiki
        And an empty wiki-scripts database

    Scenario: Syncing empty wiki
        When I synchronize the wiki-scripts database
        Then the recent changes should match
        And the logevents should match
        And the allpages lists should match
        And the revisions should match

    Scenario: Syncing empty page
        When I create page "Test"
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the allpages lists should match
        And the revisions should match

    Scenario: Syncing empty page after empty sync
        When I synchronize the wiki-scripts database
        And I create page "Test"
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the allpages lists should match
        And the revisions should match

    Scenario: Syncing edited page
        When I create page "Test"
        And I edit page "Test" to contain "aaa"
        And I synchronize the wiki-scripts database
        And I edit page "Test" to contain "bbb"
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the allpages lists should match
        And the revisions should match

    Scenario: Syncing edited page after empty sync
        When I synchronize the wiki-scripts database
        And I create page "Test"
        And I edit page "Test" to contain "aaa"
        And I synchronize the wiki-scripts database
        And I edit page "Test" to contain "bbb"
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the allpages lists should match
        And the revisions should match

    Scenario: Syncing page with displaytitle
        When I create page "Test"
        And I edit page "Test" to contain "{{DISPLAYTITLE:test}}"
        And I execute MediaWiki jobs
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the allpages lists should match
        # TODO: until we actually check the props...
        And the page_props table should not be empty
        And the revisions should match

    Scenario: Syncing page with displaytitle after empty sync
        When I synchronize the wiki-scripts database
        When I create page "Test"
        And I edit page "Test" to contain "{{DISPLAYTITLE:test}}"
        And I execute MediaWiki jobs
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the allpages lists should match
        # TODO: until we actually check the props...
        And the page_props table should not be empty
        And the revisions should match

    Scenario: Syncing protected page
        When I create page "Test"
        And I edit page "Test" to contain "test"
        And I synchronize the wiki-scripts database
        And I protect page "Test"
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the logevents should match
        And the allpages lists should match
        # TODO: until we actually check the protections...
        And the page_restrictions table should not be empty
        And the revisions should match

    Scenario: Syncing unprotected page
        When I create page "Test"
        And I edit page "Test" to contain "test"
        And I synchronize the wiki-scripts database
        And I protect page "Test"
        And I synchronize the wiki-scripts database
        And I unprotect page "Test"
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the logevents should match
        And the allpages lists should match
        And the revisions should match

    Scenario: Syncing partially protected page
        When I create page "Test"
        And I edit page "Test" to contain "test"
        And I synchronize the wiki-scripts database
        And I partially protect page "Test"
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the logevents should match
        And the allpages lists should match
        # TODO: until we actually check the protections...
        And the page_restrictions table should not be empty
        And the revisions should match

    Scenario: Syncing partially unprotected page
        When I create page "Test"
        And I edit page "Test" to contain "test"
        And I synchronize the wiki-scripts database
        And I protect page "Test"
        And I synchronize the wiki-scripts database
        And I partially unprotect page "Test"
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the logevents should match
        And the allpages lists should match
        And the revisions should match

    Scenario: Syncing moved page
        When I create page "Test 1"
        And I edit page "Test 1" to contain "test"
        And I synchronize the wiki-scripts database
        And I move page "Test 1" to "Test 2"
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the logevents should match
        And the allpages lists should match
        And the revisions should match

    Scenario: Syncing moved page without a redirect
        When I create page "Test 1"
        And I edit page "Test 1" to contain "test"
        And I synchronize the wiki-scripts database
        And I move page "Test 1" to "Test 2" without leaving a redirect
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the logevents should match
        And the allpages lists should match
        And the revisions should match

    Scenario: Syncing twice moved page
        When I create page "Test 1"
        And I edit page "Test 1" to contain "test"
        And I synchronize the wiki-scripts database
        And I move page "Test 1" to "Test 2"
        And I move page "Test 2" to "Test 3"
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the logevents should match
        And the allpages lists should match
        And the revisions should match

    Scenario: Syncing deleted page
        When I create page "Test"
        And I edit page "Test" to contain "test"
        And I synchronize the wiki-scripts database
        And I delete page "Test"
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the logevents should match
        And the allpages lists should match
        And the revisions should match

    Scenario: Syncing undeleted page
        When I create page "Test"
        And I edit page "Test" to contain "test"
        And I synchronize the wiki-scripts database
        And I delete page "Test"
        And I synchronize the wiki-scripts database
        And I undelete page "Test"
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the logevents should match
        And the allpages lists should match
        And the revisions should match

    Scenario: Syncing twice deleted page
        When I create page "Test"
        And I edit page "Test" to contain "test"
        And I delete page "Test"
        And I create page "Test"
        And I edit page "Test" to contain "test 2"
        And I delete page "Test"
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the logevents should match
        And the allpages lists should match
        And the revisions should match

    Scenario: Syncing undeleted twice deleted page
        When I create page "Test"
        And I edit page "Test" to contain "test"
        And I delete page "Test"
        And I create page "Test"
        And I edit page "Test" to contain "test 2"
        And I delete page "Test"
        And I synchronize the wiki-scripts database
        And I undelete page "Test"
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the logevents should match
        And the allpages lists should match
        And the revisions should match

    Scenario: Syncing page moved over a redirect
        When I create page "Test 2"
        And I edit page "Test 2" to contain "test"
        And I move page "Test 2" to "Test 1"
        And I synchronize the wiki-scripts database
        # edits around the move make it more difficult
        And I edit page "Test 1" to contain "test test"
        And I move page "Test 1" to "Test 2"
        And I edit page "Test 2" to contain "test"
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the logevents should match
        And the allpages lists should match
        And the revisions should match

    Scenario: Syncing deleted page with displaytitle
        When I create page "Test"
        And I edit page "Test" to contain "{{DISPLAYTITLE:test}}"
        And I execute MediaWiki jobs
        And I synchronize the wiki-scripts database
        And I delete page "Test"
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the allpages lists should match
        # TODO: until we actually check the props...
        And the page_props table should be empty
        And the revisions should match

    Scenario: Syncing deleted protected page
        When I create page "Test"
        And I edit page "Test" to contain "test"
        And I synchronize the wiki-scripts database
        And I protect page "Test"
        And I synchronize the wiki-scripts database
        And I delete page "Test"
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the logevents should match
        And the allpages lists should match
        # TODO: until we actually check the protections...
        And the page_restrictions table should be empty
        And the revisions should match

    Scenario: Syncing merged page
        When I create page "Test 1"
        And I edit page "Test 1" to contain "test 1"
        And I create page "Test 2"
        And I edit page "Test 2" to contain "test 2"
        And I synchronize the wiki-scripts database
        And I merge page "Test 1" into "Test 2"
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the logevents should match
        And the allpages lists should match
        And the revisions should match

    Scenario: Syncing merged page into new page
        When I create page "Test 1"
        And I edit page "Test 1" to contain "test 1"
        And I synchronize the wiki-scripts database
        And I create page "Test 2"
        And I edit page "Test 2" to contain "test 2"
        And I merge page "Test 1" into "Test 2"
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the logevents should match
        And the allpages lists should match
        And the revisions should match

    Scenario: Syncing deleted revision
        When I create page "Test"
        And I edit page "Test" to contain "test"
        And I synchronize the wiki-scripts database
        And I delete the oldest revision of page "Test"
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the logevents should match
        And the allpages lists should match
        And the revisions should match

    Scenario: Syncing undeleted revision
        When I create page "Test"
        And I edit page "Test" to contain "test"
        And I delete the oldest revision of page "Test"
        And I synchronize the wiki-scripts database
        And I undelete the oldest revision of page "Test"
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the logevents should match
        And the allpages lists should match
        And the revisions should match

    Scenario: Syncing deleted logevent
        When I create tag "test"
        And I synchronize the wiki-scripts database
        And I delete the first logevent
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the logevents should match
        And the allpages lists should match
        And the revisions should match

    Scenario: Syncing undeleted logevent
        When I create tag "test"
        And I delete the first logevent
        And I synchronize the wiki-scripts database
        And I undelete the first logevent
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the logevents should match
        And the allpages lists should match
        And the revisions should match

    Scenario: Syncing tagged revisions
        When I create tag "test-tag"
        And I create page "Test"
        And I edit page "Test" to contain "test"
        And I synchronize the wiki-scripts database
        And I add tag "test-tag" to all revisions of page "Test"
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the logevents should match
        And the allpages lists should match
        And the revisions should match

    Scenario: Syncing untagged revisions
        When I create tag "test-tag"
        And I create page "Test"
        And I edit page "Test" to contain "test"
        And I add tag "test-tag" to all revisions of page "Test"
        And I synchronize the wiki-scripts database
        And I remove tag "test-tag" from all revisions of page "Test"
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the logevents should match
        And the allpages lists should match
        And the revisions should match

    Scenario: Syncing tagged deleted revisions
        When I create tag "test-tag"
        And I create page "Test"
        And I edit page "Test" to contain "test"
        And I synchronize the wiki-scripts database
        # deleted revisions cannot be tagged in MediaWiki, so we delete after tagging
        And I add tag "test-tag" to all revisions of page "Test"
        And I delete page "Test"
        And I synchronize the wiki-scripts database
        # FIXME: deleted pages are not shown in list=recentchanges
        Then the recent changes should match
        And the logevents should match
        And the allpages lists should match
        And the revisions should match

    Scenario: Syncing untagged deleted revisions
        When I create tag "test-tag"
        And I create page "Test"
        And I edit page "Test" to contain "test"
        # deleted revisions cannot be tagged in MediaWiki, so we delete after tagging
        And I add tag "test-tag" to all revisions of page "Test"
        And I delete page "Test"
        And I synchronize the wiki-scripts database
        # deleted revisions cannot be tagged in MediaWiki, so we undelete before tagging
        And I undelete page "Test"
        And I remove tag "test-tag" from all revisions of page "Test"
        And I delete page "Test"
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the logevents should match
        And the allpages lists should match
        And the revisions should match

    Scenario: Syncing tagged logevent
        When I create tag "test-tag"
        And I synchronize the wiki-scripts database
        And I add tag "test-tag" to the first logevent
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the logevents should match
        And the allpages lists should match
        And the revisions should match

    Scenario: Syncing untagged logevent
        When I create tag "test-tag"
        And I add tag "test-tag" to the first logevent
        And I synchronize the wiki-scripts database
        And I remove tag "test-tag" from the first logevent
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the logevents should match
        And the allpages lists should match
        And the revisions should match

    Scenario: Syncing after import
        When I synchronize the wiki-scripts database
        And I import the testing dataset
        And I synchronize the wiki-scripts database
        Then the recent changes should match
        And the logevents should match
        And the allpages lists should match
        And the revisions should match

# FIXME: fails because deleted pages cannot be queried by page IDs
#    Scenario: Syncing after import and delete
#        When I synchronize the wiki-scripts database
#        And I import the testing dataset
#        And I delete page "Test"
#        And I synchronize the wiki-scripts database
#        Then the recent changes should match
#        And the logevents should match
#        And the allpages lists should match
#        And the revisions should match
