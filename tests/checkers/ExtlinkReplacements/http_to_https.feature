# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: ExtlinkReplacements: update http to https

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

    Scenario Outline: archlinux.org
        When the URL https://archlinux.org/some/page/ gives status 200
        And a page contains <pattern> formatted with http://archlinux.org/some/page/
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://archlinux.org/some/page/"
        And the last edit summary should be "update http to https for known domains"

    Scenario Outline: wiki.archlinux.org
        When the URL https://wiki.archlinux.org/some/page/ gives status 200
        And a page contains <pattern> formatted with http://wiki.archlinux.org/some/page/
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://wiki.archlinux.org/some/page/"
        And the last edit summary should be "update http to https for known domains"

    Scenario Outline: wiki.archlinux.org/invalid/page
        When the URL https://wiki.archlinux.org/invalid/page/ gives status 404
        And a page contains <pattern> formatted with http://wiki.archlinux.org/invalid/page/
        And I run ExtlinkReplacements
        Then the page should have the original content
        And the last edit summary should be empty

    Scenario Outline: sourceforge.net
        When the URL https://sourceforge.net/some/page/ gives status 200
        And a page contains <pattern> formatted with http://sourceforge.net/some/page/
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://sourceforge.net/some/page/"
        And the last edit summary should be "update http to https for known domains"

    Scenario Outline: www.sourceforge.net
        When the URL https://www.sourceforge.net/some/page/ gives status 200
        And a page contains <pattern> formatted with http://www.sourceforge.net/some/page/
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://www.sourceforge.net/some/page/"
        And the last edit summary should be "update http to https for known domains"

    Scenario Outline: foo.sourceforge.net
        When a page contains <pattern> formatted with http://foo.sourceforge.net/some/page/
        And I run ExtlinkReplacements
        Then the page should have the original content
        And the last edit summary should be empty
