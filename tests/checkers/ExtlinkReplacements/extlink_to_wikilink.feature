# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: ExtlinkReplacements: converting extlinks to the wiki site to wikilinks

    Scenario: Converting a wiki site URL to wikilink
        Given the wiki site URL is "https://my.wiki.org/index.php"
        When a page contains "foo https://my.wiki.org/index.php/Some_page bar"
        And I run ExtlinkReplacements
        Then the page should contain "foo [[Some page]] bar"
        And the last edit summary should be "replaced external links"

    Scenario: Converting an extlink without a title to wikilink
        Given the wiki site URL is "https://my.wiki.org/w/"
        When a page contains "foo [https://my.wiki.org/w/Some_page] bar"
        And I run ExtlinkReplacements
        Then the page should contain "foo [[Some page]] bar"
        And the last edit summary should be "replaced external links"

    Scenario: Converting an extlink with a title to wikilink
        Given the wiki site URL is "https://my.wiki.org/w/"
        When a page contains "foo [https://my.wiki.org/w/Some_page Title] bar"
        And I run ExtlinkReplacements
        Then the page should contain "foo [[Some page|Title]] bar"
        And the last edit summary should be "replaced external links"

    Scenario: Converting an extlink to a media page
        Given the wiki site URL is "https://my.wiki.org/w/"
        When a page contains "foo [https://my.wiki.org/w/Media:Foo Title] bar"
        And I run ExtlinkReplacements
        Then the page should contain "foo [[:Media:Foo|Title]] bar"
        And the last edit summary should be "replaced external links"

    Scenario: Converting an extlink to a file page
        Given the wiki site URL is "https://my.wiki.org/w/"
        When a page contains "foo [https://my.wiki.org/w/File:Foo Title] bar"
        And I run ExtlinkReplacements
        Then the page should contain "foo [[:File:Foo|Title]] bar"
        And the last edit summary should be "replaced external links"

    Scenario: Converting an extlink to a category page
        Given the wiki site URL is "https://my.wiki.org/w/"
        When a page contains "foo [https://my.wiki.org/w/Category:Foo Title] bar"
        And I run ExtlinkReplacements
        Then the page should contain "foo [[:Category:Foo|Title]] bar"
        And the last edit summary should be "replaced external links"
