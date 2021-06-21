# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: ExtlinkReplacements: extlink to wikilink or template replacements

    Scenario: Replacing a plain link to Arch bug tracker
        When a page contains "see https://bugs.archlinux.org/task/12345"
        And I run ExtlinkReplacements
        Then the page should contain "see {{Bug|12345}}"
        And the last edit summary should be "replaced external links"

    Scenario: Replacing a link to Arch bug tracker with FS 12345 title
        When a page contains "see [https://bugs.archlinux.org/task/12345 FS 12345]"
        And I run ExtlinkReplacements
        Then the page should contain "see {{Bug|12345}}"
        And the last edit summary should be "replaced external links"

    Scenario: Replacing a link to Arch bug tracker with FS#12345 title
        When a page contains "see [https://bugs.archlinux.org/task/12345 FS#12345]"
        And I run ExtlinkReplacements
        Then the page should contain "see {{Bug|12345}}"
        And the last edit summary should be "replaced external links"

    Scenario: Replacing a link to Arch bug tracker with flyspray 12345 title
        When a page contains "see [https://bugs.archlinux.org/task/12345 flyspray 12345]"
        And I run ExtlinkReplacements
        Then the page should contain "see {{Bug|12345}}"
        And the last edit summary should be "replaced external links"

    Scenario: Replacing a link to Arch bug tracker with flyspray#12345 title
        When a page contains "see [https://bugs.archlinux.org/task/12345 flyspray#12345]"
        And I run ExtlinkReplacements
        Then the page should contain "see {{Bug|12345}}"
        And the last edit summary should be "replaced external links"

    Scenario: Not replacing a link to Arch bug tracker with custom title
        When a page contains "see [https://bugs.archlinux.org/task/12345 this bug]"
        And I run ExtlinkReplacements
        Then the page should contain "see [https://bugs.archlinux.org/task/12345 this bug]"
        And the last edit summary should be empty


    Scenario: Replacing a plain www link to an Arch package
        When a page contains "install https://www.archlinux.org/packages/core/x86_64/linux/ package"
        And I run ExtlinkReplacements
        Then the page should contain "install {{Pkg|linux}} package"
        And the last edit summary should be "replaced external links"

    Scenario: Replacing a plain link to an Arch package
        When a page contains "install https://archlinux.org/packages/core/any/linux/ package"
        And I run ExtlinkReplacements
        Then the page should contain "install {{Pkg|linux}} package"
        And the last edit summary should be "replaced external links"

    Scenario: Replacing a www link to an Arch package
        When a page contains "install [https://www.archlinux.org/packages/core/x86_64/linux/ linux] package"
        And I run ExtlinkReplacements
        Then the page should contain "install {{Pkg|linux}} package"
        And the last edit summary should be "replaced external links"

    Scenario: Replacing a link to an Arch package
        When a page contains "install [https://archlinux.org/packages/core/any/linux/ linux] package"
        And I run ExtlinkReplacements
        Then the page should contain "install {{Pkg|linux}} package"
        And the last edit summary should be "replaced external links"

    Scenario: Not replacing a www link to an Arch package with a custom title
        Given the URL https://archlinux.org/packages/core/x86_64/linux/ gives status 200
        When a page contains "install [https://www.archlinux.org/packages/core/x86_64/linux/ linux package]"
        And I run ExtlinkReplacements
        Then the page should contain "install [https://archlinux.org/packages/core/x86_64/linux/ linux package]"
        And the last edit summary should be "update archweb URLs from www.archlinux.org to archlinux.org"

    Scenario: Not replacing a link to an Arch package with a custom title
        When a page contains "install [https://archlinux.org/packages/core/any/linux/ linux package]"
        And I run ExtlinkReplacements
        Then the page should contain "install [https://archlinux.org/packages/core/any/linux/ linux package]"
        And the last edit summary should be empty


    Scenario: Replacing a plain link to an AUR package
        When a page contains "install https://aur.archlinux.org/packages/linux/ package"
        And I run ExtlinkReplacements
        Then the page should contain "install {{AUR|linux}} package"
        And the last edit summary should be "replaced external links"

    Scenario: Replacing a link to an AUR package
        When a page contains "install [https://aur.archlinux.org/packages/linux/ linux] package"
        And I run ExtlinkReplacements
        Then the page should contain "install {{AUR|linux}} package"
        And the last edit summary should be "replaced external links"

    Scenario: Not replacing a link to an AUR package with a custom title
        When a page contains "install [https://aur.archlinux.org/packages/linux/ linux package]"
        And I run ExtlinkReplacements
        Then the page should contain "install [https://aur.archlinux.org/packages/linux/ linux package]"
        And the last edit summary should be empty


    Scenario: Replacing a plain link to Wikipedia
        When a page contains "see https://en.wikipedia.org/wiki/Main_page"
        And I run ExtlinkReplacements
        Then the page should contain "see [[wikipedia:Main_page]]"
        And the last edit summary should be "replaced external links"

    Scenario: Replacing a bracketed link to Wikipedia
        When a page contains "see [https://en.wikipedia.org/wiki/Main_page]"
        And I run ExtlinkReplacements
        Then the page should contain "see [[wikipedia:Main_page]]"
        And the last edit summary should be "replaced external links"

    Scenario: Replacing a link to Wikipedia with a title
        When a page contains "see [https://en.wikipedia.org/wiki/Main_page Wikipedia's main page]"
        And I run ExtlinkReplacements
        Then the page should contain "see [[wikipedia:Main_page|Wikipedia's main page]]"
        And the last edit summary should be "replaced external links"
