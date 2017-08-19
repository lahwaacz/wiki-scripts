# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Syncing the page tables

    Background:
        Given an api to an empty MediaWiki
        And an empty wiki-scripts database

    Scenario: Syncing empty wiki
        When I sync the page tables
        Then the allpages lists should match

    Scenario: Syncing empty page
        When I create page "Test"
        And I sync the page tables
        Then the allpages lists should match

    Scenario: Syncing empty page after empty sync
        When I sync the page tables
        And I create page "Test"
        And I sync the page tables
        Then the allpages lists should match

    Scenario: Syncing edited page
        When I create page "Test"
        And I edit page "Test" to contain "aaa"
        And I sync the page tables
        And I edit page "Test" to contain "bbb"
        And I sync the page tables
        Then the allpages lists should match

    Scenario: Syncing edited page after empty sync
        When I sync the page tables
        And I create page "Test"
        And I edit page "Test" to contain "aaa"
        And I sync the page tables
        And I edit page "Test" to contain "bbb"
        And I sync the page tables
        Then the allpages lists should match

    Scenario: Syncing page with displaytitle
        When I create page "Test"
        And I edit page "Test" to contain "{{DISPLAYTITLE:test}}"
        And I sync the page tables
        Then the allpages lists should match
        # TODO: until we actually check the props...
        And the page_props table should not be empty

    Scenario: Syncing page with displaytitle after empty sync
        When I sync the page tables
        When I create page "Test"
        And I edit page "Test" to contain "{{DISPLAYTITLE:test}}"
        And I sync the page tables
        Then the allpages lists should match
        # TODO: until we actually check the props...
        And the page_props table should not be empty

    Scenario: Syncing moved page
        When I create page "Test 1"
        And I edit page "Test 1" to contain "test"
        And I move page "Test 1" to "Test 2"
        And I sync the page tables
        Then the allpages lists should match

    Scenario: Syncing moved page after empty sync
        When I sync the page tables
        And I create page "Test 1"
        And I edit page "Test 1" to contain "test"
        And I move page "Test 1" to "Test 2"
        And I sync the page tables
        Then the allpages lists should match

    Scenario: Syncing moved page without a redirect
        When I create page "Test 1"
        And I edit page "Test 1" to contain "test"
        And I move page "Test 1" to "Test 2" without leaving a redirect
        And I sync the page tables
        Then the allpages lists should match

    Scenario: Syncing moved page without a redirect after empty sync
        When I sync the page tables
        And I create page "Test 1"
        And I edit page "Test 1" to contain "test"
        And I move page "Test 1" to "Test 2" without leaving a redirect
        And I sync the page tables
        Then the allpages lists should match

    Scenario: Syncing deleted page
        When I create page "Test"
        And I edit page "Test" to contain "test"
        And I sync the page tables
        And I delete page "Test"
        And I sync the page tables
        Then the allpages lists should match

    Scenario: Syncing undeleted page
        When I create page "Test"
        And I edit page "Test" to contain "test"
        And I sync the page tables
        And I delete page "Test"
        And I sync the page tables
        And I undelete page "Test"
        And I sync the page tables
        Then the allpages lists should match

    # TODO: Syncing deleted page with displaytitle
    # TODO: Syncing deleted protected page
