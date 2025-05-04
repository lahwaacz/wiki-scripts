# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: ExtlinkReplacements: update http to https

    Scenario Outline: archlinux.org
        Given the URL https://archlinux.org/some/page/ gives status 200
        When a page contains <pattern> formatted with http://archlinux.org/some/page/
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://archlinux.org/some/page/"
        And the last edit summary should be "update http to https"
    Examples:
        # parametrization of the page content - should cover all cases of an extlink
        # note: {} will be replaced with whatever is specified in each scenario
        | pattern |
        | {} |
        | [{}] |
        | [{} foo] |
        | foo {} bar |
        | foo [{}] bar |
        | foo [{} baz] bar |

    Scenario Outline: wiki.archlinux.org
        Given the URL https://wiki.archlinux.org/some/page/ gives status 200
        When a page contains <pattern> formatted with http://wiki.archlinux.org/some/page/
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://wiki.archlinux.org/some/page/"
        And the last edit summary should be "update http to https"
    Examples:
        # parametrization of the page content - should cover all cases of an extlink
        # note: {} will be replaced with whatever is specified in each scenario
        | pattern |
        | {} |
        | [{}] |
        | [{} foo] |
        | foo {} bar |
        | foo [{}] bar |
        | foo [{} baz] bar |

    Scenario Outline: wiki.archlinux.org/invalid/page
        Given the URL https://wiki.archlinux.org/invalid/page/ gives status 404
        When a page contains <pattern> formatted with http://wiki.archlinux.org/invalid/page/
        And I run ExtlinkReplacements
        Then the page should have the original content
        And the last edit summary should be empty
    Examples:
        # parametrization of the page content - should cover all cases of an extlink
        # note: {} will be replaced with whatever is specified in each scenario
        | pattern |
        | {} |
        | [{}] |
        | [{} foo] |
        | foo {} bar |
        | foo [{}] bar |
        | foo [{} baz] bar |

    Scenario Outline: sourceforge.net
        Given the URL https://sourceforge.net/some/page/ gives status 200
        When a page contains <pattern> formatted with http://sourceforge.net/some/page/
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://sourceforge.net/some/page/"
        And the last edit summary should be "update http to https"
    Examples:
        # parametrization of the page content - should cover all cases of an extlink
        # note: {} will be replaced with whatever is specified in each scenario
        | pattern |
        | {} |
        | [{}] |
        | [{} foo] |
        | foo {} bar |
        | foo [{}] bar |
        | foo [{} baz] bar |

    Scenario Outline: www.sourceforge.net
        Given the URL https://www.sourceforge.net/some/page/ gives status 200
        When a page contains <pattern> formatted with http://www.sourceforge.net/some/page/
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://www.sourceforge.net/some/page/"
        And the last edit summary should be "update http to https"
    Examples:
        # parametrization of the page content - should cover all cases of an extlink
        # note: {} will be replaced with whatever is specified in each scenario
        | pattern |
        | {} |
        | [{}] |
        | [{} foo] |
        | foo {} bar |
        | foo [{}] bar |
        | foo [{} baz] bar |

    Scenario Outline: foo.sourceforge.net
        Given the URL https://foo.sourceforge.net/some/page/ gives status 404
        When a page contains <pattern> formatted with http://foo.sourceforge.net/some/page/
        And I run ExtlinkReplacements
        Then the page should have the original content
        And the last edit summary should be empty
    Examples:
        # parametrization of the page content - should cover all cases of an extlink
        # note: {} will be replaced with whatever is specified in each scenario
        | pattern |
        | {} |
        | [{}] |
        | [{} foo] |
        | foo {} bar |
        | foo [{}] bar |
        | foo [{} baz] bar |
