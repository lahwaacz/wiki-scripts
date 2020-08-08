# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: ExtlinkReplacements: Arch projects links migration

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

    Scenario Outline: infrastructure, tree
        When the URL https://gitlab.archlinux.org/archlinux/infrastructure/tree/master/roles/docker-image gives status 200
        And a page contains <pattern> formatted with https://git.archlinux.org/infrastructure.git/tree/roles/docker-image
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://gitlab.archlinux.org/archlinux/infrastructure/tree/master/roles/docker-image"
        And the last edit summary should be "update old links to (projects|git).archlinux.org"

    Scenario Outline: infrastructure, log
        When the URL https://gitlab.archlinux.org/archlinux/infrastructure/commits/wip/mailman3 gives status 200
        And a page contains <pattern> formatted with https://git.archlinux.org/infrastructure.git/log/?h=wip/mailman3
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://gitlab.archlinux.org/archlinux/infrastructure/commits/wip/mailman3"
        And the last edit summary should be "update old links to (projects|git).archlinux.org"

    Scenario Outline: infrastructure, obsolete log
        When the URL https://gitlab.archlinux.org/archlinux/infrastructure/commits/wip/foo gives status 404
        And a page contains <pattern> formatted with https://git.archlinux.org/infrastructure.git/log/?h=wip/foo
        And I run ExtlinkReplacements
        Then the page should have the original content
        And the last edit summary should be empty

    Scenario Outline: aurweb, blob
        When the URL https://gitlab.archlinux.org/archlinux/aurweb/tree/master/doc/i18n.txt redirects to https://gitlab.archlinux.org/archlinux/aurweb/-/blob/master/doc/i18n.txt
        And the URL https://gitlab.archlinux.org/archlinux/aurweb/-/blob/master/doc/i18n.txt gives status 200
        And a page contains <pattern> formatted with https://projects.archlinux.org/aurweb.git/tree/doc/i18n.txt#n13
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://gitlab.archlinux.org/archlinux/aurweb/blob/master/doc/i18n.txt#L13"
        And the last edit summary should be "update old links to (projects|git).archlinux.org"

    Scenario Outline: archiso, obsolete blob
        When the URL https://gitlab.archlinux.org/archlinux/archiso/tree/master/configs/releng/airootfs/etc/udev/rules.d/81-dhcpcd.rules redirects to https://gitlab.archlinux.org/archlinux/archiso/-/blob/master
        And the URL https://gitlab.archlinux.org/archlinux/archiso/-/blob/master gives status 200
        And a page contains <pattern> formatted with https://git.archlinux.org/archiso.git/tree/configs/releng/airootfs/etc/udev/rules.d/81-dhcpcd.rules
        And I run ExtlinkReplacements
        Then the page should have the original content
        And the last edit summary should be empty

    Scenario Outline: aurweb, raw
        When the URL https://gitlab.archlinux.org/archlinux/aurweb/raw/master/doc/i18n.txt gives status 200
        And a page contains <pattern> formatted with https://git.archlinux.org/aurweb.git/plain/doc/i18n.txt
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://gitlab.archlinux.org/archlinux/aurweb/raw/master/doc/i18n.txt"
        And the last edit summary should be "update old links to (projects|git).archlinux.org"

    Scenario Outline: archiso, commit
        When the URL https://gitlab.archlinux.org/archlinux/archiso/commit/908370a17e6f9e64b38e9763db9357f0020ed1d9 gives status 200
        And a page contains <pattern> formatted with https://git.archlinux.org/archiso.git/commit/?id=908370a17e6f9e64b38e9763db9357f0020ed1d9
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://gitlab.archlinux.org/archlinux/archiso/commit/908370a17e6f9e64b38e9763db9357f0020ed1d9"
        And the last edit summary should be "update old links to (projects|git).archlinux.org"

    Scenario Outline: archiso, repo
        When the URL https://gitlab.archlinux.org/archlinux/archiso gives status 200
        And a page contains <pattern> formatted with https://projects.archlinux.org/archiso.git/
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://gitlab.archlinux.org/archlinux/archiso"
        And the last edit summary should be "update old links to (projects|git).archlinux.org"
