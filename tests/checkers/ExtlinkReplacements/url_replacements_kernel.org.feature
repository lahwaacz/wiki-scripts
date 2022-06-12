# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: ExtlinkReplacements: kernel.org links

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

    Scenario Outline: kernel.org fbcon.txt
        Given the URL https://docs.kernel.org/fb/fbcon.html gives status 200
        When a page contains <pattern> formatted with https://www.kernel.org/doc/Documentation/fb/fbcon.txt
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://docs.kernel.org/fb/fbcon.html"
        And the last edit summary should be "link to HTML version of kernel documentation"

    Scenario Outline: kernel.org fbcon.rst
        Given the URL https://docs.kernel.org/fb/fbcon.html gives status 200
        When a page contains <pattern> formatted with https://www.kernel.org/doc/Documentation/fb/fbcon.rst
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://docs.kernel.org/fb/fbcon.html"
        And the last edit summary should be "link to HTML version of kernel documentation"

    Scenario Outline: kernel.org fb directory
        Given the URL https://docs.kernel.org/fb/ gives status 200
        When a page contains <pattern> formatted with https://www.kernel.org/doc/Documentation/fb/
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://docs.kernel.org/fb/"
        And the last edit summary should be "link to HTML version of kernel documentation"

    Scenario Outline: not replacing excluded kernel.org link
        Given the URL https://www.kernel.org/doc/Documentation/filesystems/ gives status 200
        When a page contains <pattern> formatted with https://www.kernel.org/doc/Documentation/filesystems/
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://www.kernel.org/doc/Documentation/filesystems/"
        And the last edit summary should be empty


    Scenario Outline: wireless.kernel.org
        Given the URL https://wireless.wiki.kernel.org/ gives status 200
        When a page contains <pattern> formatted with http://wireless.kernel.org/
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://wireless.wiki.kernel.org/"
        And the last edit summary should be "update linuxwireless.org/wireless.kernel.org links"

    Scenario Outline: wireless.kernel.org iwlegacy
        Given the URL https://wireless.wiki.kernel.org/en/users/Drivers/iwlegacy gives status 200
        When a page contains <pattern> formatted with https://wireless.kernel.org/en/users/Drivers/iwlegacy
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://wireless.wiki.kernel.org/en/users/drivers/iwlegacy"
        And the last edit summary should be "update linuxwireless.org/wireless.kernel.org links"

    Scenario Outline: wireless.kernel.org iwlwifi with section
        Given the URL https://wireless.wiki.kernel.org/en/users/Drivers/iwlwifi#supported_devices gives status 200
        When a page contains <pattern> formatted with https://wireless.kernel.org/en/users/Drivers/iwlwifi#Supported_Devices
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://wireless.wiki.kernel.org/en/users/drivers/iwlwifi#supported_devices"
        And the last edit summary should be "update linuxwireless.org/wireless.kernel.org links"

    Scenario Outline: wireless.kernel.org unflag
        Given the URL https://wireless.wiki.kernel.org/en/users/Drivers/iwlegacy gives status 200
        When a page contains "[http://wireless.kernel.org/en/users/Drivers/iwlegacy iwlegacy]{{Dead link|2020|08|09}}"
        And I run ExtlinkReplacements
        Then the page should contain "[https://wireless.wiki.kernel.org/en/users/drivers/iwlegacy iwlegacy]"
        And the last edit summary should be "update linuxwireless.org/wireless.kernel.org links"

    Scenario Outline: wireless.kernel.org unflag localized
        Given the URL https://wireless.wiki.kernel.org/en/users/Drivers/iwlegacy gives status 200
        When a page contains "[http://wireless.kernel.org/en/users/Drivers/iwlegacy iwlegacy]{{Dead link (Italiano)|2020|08|09}}"
        And I run ExtlinkReplacements
        Then the page should contain "[https://wireless.wiki.kernel.org/en/users/drivers/iwlegacy iwlegacy]"
        And the last edit summary should be "update linuxwireless.org/wireless.kernel.org links"
