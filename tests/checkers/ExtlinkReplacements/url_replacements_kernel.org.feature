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
        When the URL https://www.kernel.org/doc/html/latest/fb/fbcon.html gives status 200
        And a page contains <pattern> formatted with https://www.kernel.org/doc/Documentation/fb/fbcon.txt
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://www.kernel.org/doc/html/latest/fb/fbcon.html"
        And the last edit summary should be "link to HTML version of kernel documentation"

    Scenario Outline: kernel.org fbcon.rst
        When the URL https://www.kernel.org/doc/html/latest/fb/fbcon.html gives status 200
        And a page contains <pattern> formatted with https://www.kernel.org/doc/Documentation/fb/fbcon.rst
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://www.kernel.org/doc/html/latest/fb/fbcon.html"
        And the last edit summary should be "link to HTML version of kernel documentation"

    Scenario Outline: kernel.org fb directory
        When the URL https://www.kernel.org/doc/html/latest/fb/ gives status 200
        And a page contains <pattern> formatted with https://www.kernel.org/doc/Documentation/fb/
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://www.kernel.org/doc/html/latest/fb/"
        And the last edit summary should be "link to HTML version of kernel documentation"


    Scenario Outline: wireless.kernel.org
        When the URL https://wireless.wiki.kernel.org/ gives status 200
        And a page contains <pattern> formatted with http://wireless.kernel.org/
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://wireless.wiki.kernel.org/"
        And the last edit summary should be "update wireless.kernel.org links"

    Scenario Outline: wireless.kernel.org iwlegacy
        When the URL https://wireless.wiki.kernel.org/en/users/Drivers/iwlegacy gives status 200
        And a page contains <pattern> formatted with https://wireless.kernel.org/en/users/Drivers/iwlegacy
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://wireless.wiki.kernel.org/en/users/Drivers/iwlegacy"
        And the last edit summary should be "update wireless.kernel.org links"

    Scenario Outline: wireless.kernel.org iwlwifi with section
        When the URL https://wireless.wiki.kernel.org/en/users/Drivers/iwlwifi#supported_devices gives status 200
        And a page contains <pattern> formatted with https://wireless.kernel.org/en/users/Drivers/iwlwifi#Supported_Devices
        And I run ExtlinkReplacements
        Then the page content should be "<pattern>" formatted with "https://wireless.wiki.kernel.org/en/users/Drivers/iwlwifi#supported_devices"
        And the last edit summary should be "update wireless.kernel.org links"

    Scenario Outline: wireless.kernel.org unflag
        When the URL https://wireless.wiki.kernel.org/en/users/Drivers/iwlegacy gives status 200
        And a page contains "[http://wireless.kernel.org/en/users/Drivers/iwlegacy iwlegacy]{{Dead link|2020|08|09}}"
        And I run ExtlinkReplacements
        Then the page should contain "[https://wireless.wiki.kernel.org/en/users/Drivers/iwlegacy iwlegacy]"
        And the last edit summary should be "update wireless.kernel.org links"

    Scenario Outline: wireless.kernel.org unflag localized
        When the URL https://wireless.wiki.kernel.org/en/users/Drivers/iwlegacy gives status 200
        And a page contains "[http://wireless.kernel.org/en/users/Drivers/iwlegacy iwlegacy]{{Dead link (Italiano)|2020|08|09}}"
        And I run ExtlinkReplacements
        Then the page should contain "[https://wireless.wiki.kernel.org/en/users/Drivers/iwlegacy iwlegacy]"
        And the last edit summary should be "update wireless.kernel.org links"
