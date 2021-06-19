# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: ExtlinkReplacements: strip_extra_brackets

    Scenario: Stripping extra brackets around extlink without a title
        When a page contains "[[http://example.org]]"
        And I run ExtlinkReplacements
        Then the page should contain "[http://example.org]"
        And the last edit summary should be "removed extra brackets"

    Scenario: Stripping extra brackets around extlink with a title
        When a page contains "[[http://example.org link title]]"
        And I run ExtlinkReplacements
        Then the page should contain "[http://example.org link title]"
        And the last edit summary should be "removed extra brackets"

    Scenario: Not stripping extra bracket left of an extlink
        When a page contains "[[http://example.org]"
        And I run ExtlinkReplacements
        Then the page should contain "[[http://example.org]"
        And the last edit summary should be empty

    Scenario: Not stripping extra bracket right of an extlink
        When a page contains "[http://example.org]]"
        And I run ExtlinkReplacements
        Then the page should contain "[http://example.org]]"
        And the last edit summary should be empty

    Scenario: Not stripping brackets from normal extlink
        When a page contains "[[foo]][http://example.org][[bar]]"
        And I run ExtlinkReplacements
        Then the page should contain "[[foo]][http://example.org][[bar]]"
        And the last edit summary should be empty
