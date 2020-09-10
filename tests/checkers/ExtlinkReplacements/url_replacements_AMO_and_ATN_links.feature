# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: ExtlinkReplacements: remove language codes from AMO and ATN links

    Examples:
        # parametrization of the page content - should cover all cases of an extlink
        # note: {} will be replaced with whatever is specified in each scenario)
        | pattern |
        | {} |
        | [{}] |
        | [{} foo] |
        | foo {} bar |
        | foo [{}] bar |
        | foo [{} baz] bar |

    Scenario Outline: AMO, firefox
        Given the URL https://addons.mozilla.org/firefox/search-tools/ gives status 200
        When a page contains <pattern> formatted with https://addons.mozilla.org/firefox/search-tools/
        And I run ExtlinkReplacements
        Then the page should have the original content
        And the last edit summary should be empty

    Scenario Outline: AMO, firefox, lang
        Given the URL https://addons.mozilla.org/firefox/search-tools/ gives status 200
        When a page contains <pattern> formatted with https://addons.mozilla.org/en-US/firefox/search-tools/
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://addons.mozilla.org/firefox/search-tools/"
        And the last edit summary should be "remove language codes from addons.mozilla.org and addons.thunderbird.net links"

    Scenario Outline: AMO, android, lang
        Given the URL https://addons.mozilla.org/android/foo/bar/?baz gives status 200
        When a page contains <pattern> formatted with https://addons.mozilla.org/en-US/android/foo/bar/?baz
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://addons.mozilla.org/android/foo/bar/?baz"
        And the last edit summary should be "remove language codes from addons.mozilla.org and addons.thunderbird.net links"

    Scenario Outline: AMO, thunderbird
        Given the URL https://addons.thunderbird.net/thunderbird/addon/enigmail/ gives status 200
        When a page contains <pattern> formatted with https://addons.mozilla.org/thunderbird/addon/enigmail/
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://addons.thunderbird.net/thunderbird/addon/enigmail/"
        And the last edit summary should be "update links from addons.mozilla.org to addons.thunderbird.net"

    Scenario Outline: AMO, seamonkey
        Given the URL https://addons.thunderbird.net/seamonkey/foo/bar/?baz gives status 200
        When a page contains <pattern> formatted with https://addons.mozilla.org/seamonkey/foo/bar/?baz
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://addons.thunderbird.net/seamonkey/foo/bar/?baz"
        And the last edit summary should be "update links from addons.mozilla.org to addons.thunderbird.net"

    Scenario Outline: AMO, thunderbird, lang
        Given the URL https://addons.thunderbird.net/thunderbird/addon/enigmail/ gives status 200
        When a page contains <pattern> formatted with https://addons.mozilla.org/en-US/thunderbird/addon/enigmail/
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://addons.thunderbird.net/thunderbird/addon/enigmail/"
        And the last edit summary should be "remove language codes from addons.mozilla.org and addons.thunderbird.net links"

    Scenario Outline: AMO, seamonkey, lang
        Given the URL https://addons.thunderbird.net/seamonkey/foo/bar/?baz gives status 200
        When a page contains <pattern> formatted with https://addons.mozilla.org/some-lang/seamonkey/foo/bar/?baz
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://addons.thunderbird.net/seamonkey/foo/bar/?baz"
        And the last edit summary should be "remove language codes from addons.mozilla.org and addons.thunderbird.net links"

    Scenario Outline: ATN, thunderbird
        Given the URL https://addons.thunderbird.net/thunderbird/addon/enigmail/ gives status 200
        When a page contains <pattern> formatted with https://addons.thunderbird.net/thunderbird/addon/enigmail/
        And I run ExtlinkReplacements
        Then the page should have the original content
        And the last edit summary should be empty

    Scenario Outline: ATN, thunderbird, lang
        Given the URL https://addons.thunderbird.net/thunderbird/addon/enigmail/ gives status 200
        When a page contains <pattern> formatted with https://addons.thunderbird.net/en-US/thunderbird/addon/enigmail/
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://addons.thunderbird.net/thunderbird/addon/enigmail/"
        And the last edit summary should be "remove language codes from addons.mozilla.org and addons.thunderbird.net links"
