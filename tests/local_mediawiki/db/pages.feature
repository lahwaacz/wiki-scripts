# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Syncing the page tables

    Background:
        Given an api to an empty MediaWiki
        And an empty wiki-scripts database

    Scenario: Syncing empty wiki
        When I sync the page tables
        Then the allpages lists should match

    Scenario: Syncing page
        When I create page "Test"
        And I sync the page tables
        Then the allpages lists should match

    Scenario: Syncing page after empty
        When I sync the page tables
        And I create page "Test 1"
        And I sync the page tables
        Then the allpages lists should match
