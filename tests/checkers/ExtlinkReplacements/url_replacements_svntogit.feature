# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: ExtlinkReplacements: svntogit links migration

    Background:
        Given these working URLs:
            # packages, commit
            | https://github.com/archlinux/svntogit-packages/commit/c46609a4b0325c363455264844091b71de01eddc |
            # packages, blob
            | https://github.com/archlinux/svntogit-packages/blob/packages/sudo/trunk/PKGBUILD |
            # packages, raw
            | https://github.com/archlinux/svntogit-packages/raw/packages/sudo/trunk/PKGBUILD |
            # packages, log
            | https://github.com/archlinux/svntogit-packages/commits/packages/grub/trunk |
            # packages, repo
            | https://github.com/archlinux/svntogit-packages |
            # community, commit
            | https://github.com/archlinux/svntogit-community/blob/91e4262f91ee883ba9766ee61097027c3bfa88f5/trunk/PKGBUILD#L56 |
            # community, blob
            | https://github.com/archlinux/svntogit-community/blob/packages/mpv/trunk/PKGBUILD#L42 |
            # community, raw
            | https://github.com/archlinux/svntogit-community/raw/packages/mpv/trunk/PKGBUILD |
            # community, log
            | https://github.com/archlinux/svntogit-community/commits/packages/mpv/trunk |
            # community, repo
            | https://github.com/archlinux/svntogit-community |

    Scenario Outline: packages, commit
        When a page contains <pattern> formatted with <url>
        And I run ExtlinkReplacements
        Then the <url> should be replaced with "https://github.com/archlinux/svntogit-packages/commit/c46609a4b0325c363455264844091b71de01eddc"
        And the last edit summary should be "update svntogit URLs from (projects|git).archlinux.org to github.com"
    Examples:
        # parametrization of the scenario - should cover all cases of an extlink
        # note: {} will be replaced with the URL
        | pattern          | url                                                                                                      |
        | {}               | https://projects.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc |
        | {}               | https://git.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc      |
        | [{}]             | https://projects.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc |
        | [{}]             | https://git.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc      |
        | [{} foo]         | https://projects.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc |
        | [{} foo]         | https://git.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc      |
        | foo {} bar       | https://projects.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc |
        | foo {} bar       | https://git.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc      |
        | foo [{}] bar     | https://projects.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc |
        | foo [{}] bar     | https://git.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc      |
        | foo [{} baz] bar | https://projects.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc |
        | foo [{} baz] bar | https://git.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc      |

    Scenario Outline: packages, blob
        When a page contains <pattern> formatted with <url>
        And I run ExtlinkReplacements
        Then the <url> should be replaced with "https://github.com/archlinux/svntogit-packages/blob/packages/sudo/trunk/PKGBUILD"
        And the last edit summary should be "update svntogit URLs from (projects|git).archlinux.org to github.com"
    Examples:
        # parametrization of the scenario - should cover all cases of an extlink
        # note: {} will be replaced with the URL
        | pattern          | url                                                                           |
        | {}               | https://projects.archlinux.org/svntogit/packages.git/tree/sudo/trunk/PKGBUILD |
        | {}               | https://git.archlinux.org/svntogit/packages.git/tree/sudo/trunk/PKGBUILD      |
        | [{}]             | https://projects.archlinux.org/svntogit/packages.git/tree/sudo/trunk/PKGBUILD |
        | [{}]             | https://git.archlinux.org/svntogit/packages.git/tree/sudo/trunk/PKGBUILD      |
        | [{} foo]         | https://projects.archlinux.org/svntogit/packages.git/tree/sudo/trunk/PKGBUILD |
        | [{} foo]         | https://git.archlinux.org/svntogit/packages.git/tree/sudo/trunk/PKGBUILD      |
        | foo {} bar       | https://projects.archlinux.org/svntogit/packages.git/tree/sudo/trunk/PKGBUILD |
        | foo {} bar       | https://git.archlinux.org/svntogit/packages.git/tree/sudo/trunk/PKGBUILD      |
        | foo [{}] bar     | https://projects.archlinux.org/svntogit/packages.git/tree/sudo/trunk/PKGBUILD |
        | foo [{}] bar     | https://git.archlinux.org/svntogit/packages.git/tree/sudo/trunk/PKGBUILD      |
        | foo [{} baz] bar | https://projects.archlinux.org/svntogit/packages.git/tree/sudo/trunk/PKGBUILD |
        | foo [{} baz] bar | https://git.archlinux.org/svntogit/packages.git/tree/sudo/trunk/PKGBUILD      |

    Scenario Outline: packages, raw
        When a page contains <pattern> formatted with <url>
        And I run ExtlinkReplacements
        Then the <url> should be replaced with "https://github.com/archlinux/svntogit-packages/raw/packages/sudo/trunk/PKGBUILD"
        And the last edit summary should be "update svntogit URLs from (projects|git).archlinux.org to github.com"
    Examples:
        # parametrization of the scenario - should cover all cases of an extlink
        # note: {} will be replaced with the URL
        | pattern          | url                                                                            |
        | {}               | https://projects.archlinux.org/svntogit/packages.git/plain/sudo/trunk/PKGBUILD |
        | {}               | https://git.archlinux.org/svntogit/packages.git/plain/sudo/trunk/PKGBUILD      |
        | [{}]             | https://projects.archlinux.org/svntogit/packages.git/plain/sudo/trunk/PKGBUILD |
        | [{}]             | https://git.archlinux.org/svntogit/packages.git/plain/sudo/trunk/PKGBUILD      |
        | [{} foo]         | https://projects.archlinux.org/svntogit/packages.git/plain/sudo/trunk/PKGBUILD |
        | [{} foo]         | https://git.archlinux.org/svntogit/packages.git/plain/sudo/trunk/PKGBUILD      |
        | foo {} bar       | https://projects.archlinux.org/svntogit/packages.git/plain/sudo/trunk/PKGBUILD |
        | foo {} bar       | https://git.archlinux.org/svntogit/packages.git/plain/sudo/trunk/PKGBUILD      |
        | foo [{}] bar     | https://projects.archlinux.org/svntogit/packages.git/plain/sudo/trunk/PKGBUILD |
        | foo [{}] bar     | https://git.archlinux.org/svntogit/packages.git/plain/sudo/trunk/PKGBUILD      |
        | foo [{} baz] bar | https://projects.archlinux.org/svntogit/packages.git/plain/sudo/trunk/PKGBUILD |
        | foo [{} baz] bar | https://git.archlinux.org/svntogit/packages.git/plain/sudo/trunk/PKGBUILD      |

    Scenario Outline: packages, log
        When a page contains <pattern> formatted with <url>
        And I run ExtlinkReplacements
        Then the <url> should be replaced with "https://github.com/archlinux/svntogit-packages/commits/packages/grub/trunk"
        And the last edit summary should be "update svntogit URLs from (projects|git).archlinux.org to github.com"
    Examples:
        # parametrization of the scenario - should cover all cases of an extlink
        # note: {} will be replaced with the URL
        | pattern          | url                                                                            |
        | {}               | https://projects.archlinux.org/svntogit/packages.git/log/trunk?h=packages/grub |
        | {}               | https://git.archlinux.org/svntogit/packages.git/log/trunk?h=packages/grub      |
        | [{}]             | https://projects.archlinux.org/svntogit/packages.git/log/trunk?h=packages/grub |
        | [{}]             | https://git.archlinux.org/svntogit/packages.git/log/trunk?h=packages/grub      |
        | [{} foo]         | https://projects.archlinux.org/svntogit/packages.git/log/trunk?h=packages/grub |
        | [{} foo]         | https://git.archlinux.org/svntogit/packages.git/log/trunk?h=packages/grub      |
        | foo {} bar       | https://projects.archlinux.org/svntogit/packages.git/log/trunk?h=packages/grub |
        | foo {} bar       | https://git.archlinux.org/svntogit/packages.git/log/trunk?h=packages/grub      |
        | foo [{}] bar     | https://projects.archlinux.org/svntogit/packages.git/log/trunk?h=packages/grub |
        | foo [{}] bar     | https://git.archlinux.org/svntogit/packages.git/log/trunk?h=packages/grub      |
        | foo [{} baz] bar | https://projects.archlinux.org/svntogit/packages.git/log/trunk?h=packages/grub |
        | foo [{} baz] bar | https://git.archlinux.org/svntogit/packages.git/log/trunk?h=packages/grub      |

    Scenario Outline: packages, repo
        When a page contains <pattern> formatted with <url>
        And I run ExtlinkReplacements
        Then the <url> should be replaced with "https://github.com/archlinux/svntogit-packages"
        And the last edit summary should be "update svntogit URLs from (projects|git).archlinux.org to github.com"
    Examples:
        # parametrization of the scenario - should cover all cases of an extlink
        # note: {} will be replaced with the URL
        | pattern          | url                                                       |
        | {}               | https://projects.archlinux.org/svntogit/packages.git      |
        | {}               | https://projects.archlinux.org/svntogit/packages.git/tree |
        | {}               | https://git.archlinux.org/svntogit/packages.git           |
        | {}               | https://git.archlinux.org/svntogit/packages.git/tree      |
        | [{}]             | https://projects.archlinux.org/svntogit/packages.git      |
        | [{}]             | https://projects.archlinux.org/svntogit/packages.git/tree |
        | [{}]             | https://git.archlinux.org/svntogit/packages.git           |
        | [{}]             | https://git.archlinux.org/svntogit/packages.git/tree      |
        | [{} foo]         | https://projects.archlinux.org/svntogit/packages.git      |
        | [{} foo]         | https://projects.archlinux.org/svntogit/packages.git/tree |
        | [{} foo]         | https://git.archlinux.org/svntogit/packages.git           |
        | [{} foo]         | https://git.archlinux.org/svntogit/packages.git/tree      |
        | foo {} bar       | https://projects.archlinux.org/svntogit/packages.git      |
        | foo {} bar       | https://projects.archlinux.org/svntogit/packages.git/tree |
        | foo {} bar       | https://git.archlinux.org/svntogit/packages.git           |
        | foo {} bar       | https://git.archlinux.org/svntogit/packages.git/tree      |
        | foo [{}] bar     | https://projects.archlinux.org/svntogit/packages.git      |
        | foo [{}] bar     | https://projects.archlinux.org/svntogit/packages.git/tree |
        | foo [{}] bar     | https://git.archlinux.org/svntogit/packages.git           |
        | foo [{}] bar     | https://git.archlinux.org/svntogit/packages.git/tree      |
        | foo [{} baz] bar | https://projects.archlinux.org/svntogit/packages.git      |
        | foo [{} baz] bar | https://projects.archlinux.org/svntogit/packages.git/tree |
        | foo [{} baz] bar | https://git.archlinux.org/svntogit/packages.git           |
        | foo [{} baz] bar | https://git.archlinux.org/svntogit/packages.git/tree      |

    Scenario Outline: community, commit
        When a page contains <pattern> formatted with <url>
        And I run ExtlinkReplacements
        Then the <url> should be replaced with "https://github.com/archlinux/svntogit-community/blob/91e4262f91ee883ba9766ee61097027c3bfa88f5/trunk/PKGBUILD#L56"
        And the last edit summary should be "update svntogit URLs from (projects|git).archlinux.org to github.com"
    Examples:
        # parametrization of the scenario - should cover all cases of an extlink
        # note: {} will be replaced with the URL
        | pattern          | url                                                                                          |
        | {}               | https://projects.archlinux.org/svntogit/community.git/tree/trunk/PKGBUILD?h=packages/nextcloud&id=91e4262f91ee883ba9766ee61097027c3bfa88f5#n56 |
        | {}               | https://git.archlinux.org/svntogit/community.git/tree/trunk/PKGBUILD?h=packages/nextcloud&id=91e4262f91ee883ba9766ee61097027c3bfa88f5#n56    |
        | [{}]             | https://projects.archlinux.org/svntogit/community.git/tree/trunk/PKGBUILD?h=packages/nextcloud&id=91e4262f91ee883ba9766ee61097027c3bfa88f5#n56 |
        | [{}]             | https://git.archlinux.org/svntogit/community.git/tree/trunk/PKGBUILD?h=packages/nextcloud&id=91e4262f91ee883ba9766ee61097027c3bfa88f5#n56    |
        | [{} foo]         | https://projects.archlinux.org/svntogit/community.git/tree/trunk/PKGBUILD?h=packages/nextcloud&id=91e4262f91ee883ba9766ee61097027c3bfa88f5#n56 |
        | [{} foo]         | https://git.archlinux.org/svntogit/community.git/tree/trunk/PKGBUILD?h=packages/nextcloud&id=91e4262f91ee883ba9766ee61097027c3bfa88f5#n56    |
        | foo {} bar       | https://projects.archlinux.org/svntogit/community.git/tree/trunk/PKGBUILD?h=packages/nextcloud&id=91e4262f91ee883ba9766ee61097027c3bfa88f5#n56 |
        | foo {} bar       | https://git.archlinux.org/svntogit/community.git/tree/trunk/PKGBUILD?h=packages/nextcloud&id=91e4262f91ee883ba9766ee61097027c3bfa88f5#n56    |
        | foo [{}] bar     | https://projects.archlinux.org/svntogit/community.git/tree/trunk/PKGBUILD?h=packages/nextcloud&id=91e4262f91ee883ba9766ee61097027c3bfa88f5#n56 |
        | foo [{}] bar     | https://git.archlinux.org/svntogit/community.git/tree/trunk/PKGBUILD?h=packages/nextcloud&id=91e4262f91ee883ba9766ee61097027c3bfa88f5#n56    |
        | foo [{} baz] bar | https://projects.archlinux.org/svntogit/community.git/tree/trunk/PKGBUILD?h=packages/nextcloud&id=91e4262f91ee883ba9766ee61097027c3bfa88f5#n56 |
        | foo [{} baz] bar | https://git.archlinux.org/svntogit/community.git/tree/trunk/PKGBUILD?h=packages/nextcloud&id=91e4262f91ee883ba9766ee61097027c3bfa88f5#n56    |

    Scenario Outline: community, blob
        When a page contains <pattern> formatted with <url>
        And I run ExtlinkReplacements
        Then the <url> should be replaced with "https://github.com/archlinux/svntogit-community/blob/packages/mpv/trunk/PKGBUILD#L42"
        And the last edit summary should be "update svntogit URLs from (projects|git).archlinux.org to github.com"
    Examples:
        # parametrization of the scenario - should cover all cases of an extlink
        # note: {} will be replaced with the URL
        | pattern          | url                                                                               |
        | {}               | https://projects.archlinux.org/svntogit/community.git/tree/mpv/trunk/PKGBUILD#n42 |
        | {}               | https://git.archlinux.org/svntogit/community.git/tree/mpv/trunk/PKGBUILD#n42      |
        | [{}]             | https://projects.archlinux.org/svntogit/community.git/tree/mpv/trunk/PKGBUILD#n42 |
        | [{}]             | https://git.archlinux.org/svntogit/community.git/tree/mpv/trunk/PKGBUILD#n42      |
        | [{} foo]         | https://projects.archlinux.org/svntogit/community.git/tree/mpv/trunk/PKGBUILD#n42 |
        | [{} foo]         | https://git.archlinux.org/svntogit/community.git/tree/mpv/trunk/PKGBUILD#n42      |
        | foo {} bar       | https://projects.archlinux.org/svntogit/community.git/tree/mpv/trunk/PKGBUILD#n42 |
        | foo {} bar       | https://git.archlinux.org/svntogit/community.git/tree/mpv/trunk/PKGBUILD#n42      |
        | foo [{}] bar     | https://projects.archlinux.org/svntogit/community.git/tree/mpv/trunk/PKGBUILD#n42 |
        | foo [{}] bar     | https://git.archlinux.org/svntogit/community.git/tree/mpv/trunk/PKGBUILD#n42      |
        | foo [{} baz] bar | https://projects.archlinux.org/svntogit/community.git/tree/mpv/trunk/PKGBUILD#n42 |
        | foo [{} baz] bar | https://git.archlinux.org/svntogit/community.git/tree/mpv/trunk/PKGBUILD#n42      |

    Scenario Outline: community, raw
        When a page contains <pattern> formatted with <url>
        And I run ExtlinkReplacements
        Then the <url> should be replaced with "https://github.com/archlinux/svntogit-community/raw/packages/mpv/trunk/PKGBUILD"
        And the last edit summary should be "update svntogit URLs from (projects|git).archlinux.org to github.com"
    Examples:
        # parametrization of the scenario - should cover all cases of an extlink
        # note: {} will be replaced with the URL
        | pattern          | url                                                                            |
        | {}               | https://projects.archlinux.org/svntogit/community.git/plain/mpv/trunk/PKGBUILD |
        | {}               | https://git.archlinux.org/svntogit/community.git/plain/mpv/trunk/PKGBUILD      |
        | [{}]             | https://projects.archlinux.org/svntogit/community.git/plain/mpv/trunk/PKGBUILD |
        | [{}]             | https://git.archlinux.org/svntogit/community.git/plain/mpv/trunk/PKGBUILD      |
        | [{} foo]         | https://projects.archlinux.org/svntogit/community.git/plain/mpv/trunk/PKGBUILD |
        | [{} foo]         | https://git.archlinux.org/svntogit/community.git/plain/mpv/trunk/PKGBUILD      |
        | foo {} bar       | https://projects.archlinux.org/svntogit/community.git/plain/mpv/trunk/PKGBUILD |
        | foo {} bar       | https://git.archlinux.org/svntogit/community.git/plain/mpv/trunk/PKGBUILD      |
        | foo [{}] bar     | https://projects.archlinux.org/svntogit/community.git/plain/mpv/trunk/PKGBUILD |
        | foo [{}] bar     | https://git.archlinux.org/svntogit/community.git/plain/mpv/trunk/PKGBUILD      |
        | foo [{} baz] bar | https://projects.archlinux.org/svntogit/community.git/plain/mpv/trunk/PKGBUILD |
        | foo [{} baz] bar | https://git.archlinux.org/svntogit/community.git/plain/mpv/trunk/PKGBUILD      |

    Scenario Outline: community, log
        When a page contains <pattern> formatted with <url>
        And I run ExtlinkReplacements
        Then the <url> should be replaced with "https://github.com/archlinux/svntogit-community/commits/packages/mpv/trunk"
        And the last edit summary should be "update svntogit URLs from (projects|git).archlinux.org to github.com"
    Examples:
        # parametrization of the scenario - should cover all cases of an extlink
        # note: {} will be replaced with the URL
        | pattern          | url                                                                            |
        | {}               | https://projects.archlinux.org/svntogit/community.git/log/trunk?h=packages/mpv |
        | {}               | https://git.archlinux.org/svntogit/community.git/log/trunk?h=packages/mpv      |
        | [{}]             | https://projects.archlinux.org/svntogit/community.git/log/trunk?h=packages/mpv |
        | [{}]             | https://git.archlinux.org/svntogit/community.git/log/trunk?h=packages/mpv      |
        | [{} foo]         | https://projects.archlinux.org/svntogit/community.git/log/trunk?h=packages/mpv |
        | [{} foo]         | https://git.archlinux.org/svntogit/community.git/log/trunk?h=packages/mpv      |
        | foo {} bar       | https://projects.archlinux.org/svntogit/community.git/log/trunk?h=packages/mpv |
        | foo {} bar       | https://git.archlinux.org/svntogit/community.git/log/trunk?h=packages/mpv      |
        | foo [{}] bar     | https://projects.archlinux.org/svntogit/community.git/log/trunk?h=packages/mpv |
        | foo [{}] bar     | https://git.archlinux.org/svntogit/community.git/log/trunk?h=packages/mpv      |
        | foo [{} baz] bar | https://projects.archlinux.org/svntogit/community.git/log/trunk?h=packages/mpv |
        | foo [{} baz] bar | https://git.archlinux.org/svntogit/community.git/log/trunk?h=packages/mpv      |

    Scenario Outline: community, repo
        When a page contains <pattern> formatted with <url>
        And I run ExtlinkReplacements
        Then the <url> should be replaced with "https://github.com/archlinux/svntogit-packages"
        And the last edit summary should be "update svntogit URLs from (projects|git).archlinux.org to github.com"
    Examples:
        # parametrization of the scenario - should cover all cases of an extlink
        # note: {} will be replaced with the URL
        | pattern          | url                                                       |
        | {}               | https://projects.archlinux.org/svntogit/packages.git      |
        | {}               | https://projects.archlinux.org/svntogit/packages.git/tree |
        | {}               | https://git.archlinux.org/svntogit/packages.git           |
        | {}               | https://git.archlinux.org/svntogit/packages.git/tree      |
        | [{}]             | https://projects.archlinux.org/svntogit/packages.git      |
        | [{}]             | https://projects.archlinux.org/svntogit/packages.git/tree |
        | [{}]             | https://git.archlinux.org/svntogit/packages.git           |
        | [{}]             | https://git.archlinux.org/svntogit/packages.git/tree      |
        | [{} foo]         | https://projects.archlinux.org/svntogit/packages.git      |
        | [{} foo]         | https://projects.archlinux.org/svntogit/packages.git/tree |
        | [{} foo]         | https://git.archlinux.org/svntogit/packages.git           |
        | [{} foo]         | https://git.archlinux.org/svntogit/packages.git/tree      |
        | foo {} bar       | https://projects.archlinux.org/svntogit/packages.git      |
        | foo {} bar       | https://projects.archlinux.org/svntogit/packages.git/tree |
        | foo {} bar       | https://git.archlinux.org/svntogit/packages.git           |
        | foo {} bar       | https://git.archlinux.org/svntogit/packages.git/tree      |
        | foo [{}] bar     | https://projects.archlinux.org/svntogit/packages.git      |
        | foo [{}] bar     | https://projects.archlinux.org/svntogit/packages.git/tree |
        | foo [{}] bar     | https://git.archlinux.org/svntogit/packages.git           |
        | foo [{}] bar     | https://git.archlinux.org/svntogit/packages.git/tree      |
        | foo [{} baz] bar | https://projects.archlinux.org/svntogit/packages.git      |
        | foo [{} baz] bar | https://projects.archlinux.org/svntogit/packages.git/tree |
        | foo [{} baz] bar | https://git.archlinux.org/svntogit/packages.git           |
        | foo [{} baz] bar | https://git.archlinux.org/svntogit/packages.git/tree      |

    Scenario Outline: broken on git.archlinux.org
        Given these broken URLs:
            | https://projects.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc |
            | https://git.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc |
            | https://github.com/archlinux/svntogit-packages/commit/c46609a4b0325c363455264844091b71de01eddc |
        When a page contains <pattern> formatted with <url>
        And I run ExtlinkReplacements
        Then the page should have the original content
        And the last edit summary should be empty
    Examples:
        # parametrization of the scenario - should cover all cases of an extlink
        # note: {} will be replaced with the URL
        | pattern          | url                                                                                                      |
        | {}               | https://projects.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc |
        | {}               | https://git.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc      |
        | [{}]             | https://projects.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc |
        | [{}]             | https://git.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc      |
        | [{} foo]         | https://projects.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc |
        | [{} foo]         | https://git.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc      |
        | foo {} bar       | https://projects.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc |
        | foo {} bar       | https://git.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc      |
        | foo [{}] bar     | https://projects.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc |
        | foo [{}] bar     | https://git.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc      |
        | foo [{} baz] bar | https://projects.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc |
        | foo [{} baz] bar | https://git.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc      |

    Scenario Outline: broken on github.com
        Given these broken URLs:
            | https://github.com/archlinux/svntogit-packages/commit/c46609a4b0325c363455264844091b71de01eddc |
        When a page contains <pattern> formatted with <url>
        And I run ExtlinkReplacements
        Then the page should have the original content
        And the last edit summary should be empty
    Examples:
        # parametrization of the scenario - should cover all cases of an extlink
        # note: {} will be replaced with the URL
        | pattern          | url                                                                                                      |
        | {}               | https://projects.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc |
        | {}               | https://git.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc      |
        | [{}]             | https://projects.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc |
        | [{}]             | https://git.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc      |
        | [{} foo]         | https://projects.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc |
        | [{} foo]         | https://git.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc      |
        | foo {} bar       | https://projects.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc |
        | foo {} bar       | https://git.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc      |
        | foo [{}] bar     | https://projects.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc |
        | foo [{}] bar     | https://git.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc      |
        | foo [{} baz] bar | https://projects.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc |
        | foo [{} baz] bar | https://git.archlinux.org/svntogit/packages.git/commit/?id=c46609a4b0325c363455264844091b71de01eddc      |
