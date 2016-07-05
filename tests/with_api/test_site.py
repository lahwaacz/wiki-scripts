#! /usr/bin/env python3

from nose.tools import assert_equals, assert_false, raises
from nose.plugins.attrib import attr

from . import fixtures

from ws.core.api import LoginFailed

@attr(speed="slow")
class test_site:
    """
    Tests intended mostly for detecting changes in the ArchWiki configuration.
    """

    props_data = {
        "usergroups": [
            {
                "name": "*",
                "rights": [
                    "createaccount",
                    "read",
                    "createpage",
                    "createtalk",
                    "editmyusercss",
                    "editmyuserjs",
                    "viewmywatchlist",
                    "editmywatchlist",
                    "viewmyprivateinfo",
                    "editmyprivateinfo",
                    "editmyoptions",
                    "abusefilter-log-detail",
                    "abusefilter-view",
                    "abusefilter-log"
                ]
            },
            {
                "name": "user",
                "rights": [
                    "move",
                    "move-subpages",
                    "move-rootuserpages",
                    "move-categorypages",
                    "movefile",
                    "read",
                    "edit",
                    "createpage",
                    "createtalk",
                    "minoredit",
                    "purge",
                    "sendemail",
                    "applychangetags",
                    "changetags"
                ]
            },
            {
                "name": "autoconfirmed",
                "rights": [
                    "autoconfirmed",
                    "editsemiprotected",
                    "writeapi"
                ]
            },
            {
                "name": "bot",
                "rights": [
                    "bot",
                    "autoconfirmed",
                    "editsemiprotected",
                    "nominornewtalk",
                    "autopatrol",
                    "suppressredirect",
                    "apihighlimits",
                    "writeapi"
                ]
            },
            {
                "name": "sysop",
                "rights": [
                    "block",
                    "createaccount",
                    "delete",
                    "bigdelete",
                    "deletedhistory",
                    "deletedtext",
                    "undelete",
                    "editinterface",
                    "editusercss",
                    "edituserjs",
                    "import",
                    "importupload",
                    "move",
                    "move-subpages",
                    "move-rootuserpages",
                    "move-categorypages",
                    "patrol",
                    "autopatrol",
                    "protect",
                    "editprotected",
                    "proxyunbannable",
                    "rollback",
                    "upload",
                    "reupload",
                    "reupload-shared",
                    "unwatchedpages",
                    "autoconfirmed",
                    "editsemiprotected",
                    "ipblock-exempt",
                    "blockemail",
                    "markbotedits",
                    "apihighlimits",
                    "browsearchive",
                    "noratelimit",
                    "movefile",
                    "unblockself",
                    "suppressredirect",
                    "mergehistory",
                    "managechangetags",
                    "deleterevision",
                    "writeapi",
                    "abusefilter-modify",
                    "abusefilter-private",
                    "abusefilter-modify-restricted",
                    "abusefilter-revert",
                    "checkuser",
                    "checkuser-log",
                    "nuke"
                ]
            },
            {
                "name": "bureaucrat",
                "rights": [
                    "userrights",
                    "noratelimit"
                ]
            },
            {
                "name": "maintainer",
                "rights": [
                    "autopatrol",
                    "patrol",
                    "noratelimit",
                    "suppressredirect",
                    "rollback",
                    "browsearchive",
                    "apihighlimits",
                    "unwatchedpages",
                    "deletedhistory",
                    "deletedtext",
                    "writeapi"
                ]
            },
            {
                "name": "checkuser",
                "rights": [
                    "checkuser",
                    "checkuser-log"
                ]
            }
        ],
        "extensions": [
            {
                "type": "other",
                "name": "FunnyQuestion",
                "description": "Challenge-response authentication",
                "author": "Pierre Schmitz",
                "url": "https://pierre-schmitz.com/",
                "version": "2.3"
            },
            {
                "type": "antispam",
                "name": "Abuse Filter",
                "descriptionmsg": "abusefilter-desc",
                "author": "Andrew Garrett, River Tarnell, Victor Vasiliev, Marius Hoch",
                "url": "https://www.mediawiki.org/wiki/Extension:AbuseFilter",
                "license-name": "GPL-2.0+",
                "license": "/index.php/Special:Version/License/Abuse_Filter"
            },
            {
                "type": "skin",
                "name": "ArchLinux",
                "description": "MediaWiki skin based on MonoBook",
                "author": "Pierre Schmitz",
                "url": "https://www.archlinux.org",
                "license-name": "GPL-2.0+",
                "license": "/index.php/Special:Version/License/ArchLinux"
            },
            {
                "type": "specialpage",
                "name": "Nuke",
                "descriptionmsg": "nuke-desc",
                "author": "Brion Vibber, Jeroen De Dauw",
                "url": "https://www.mediawiki.org/wiki/Extension:Nuke",
                "version": "1.2.0",
                "license-name": "GPL-2.0+",
                "license": "/index.php/Special:Version/License/Nuke"
            },
            {
                "type": "specialpage",
                "name": "CheckUser",
                "descriptionmsg": "checkuser-desc",
                "author": "Tim Starling, Aaron Schulz",
                "url": "https://www.mediawiki.org/wiki/Extension:CheckUser",
                "version": "2.4",
                "license-name": "GPL-2.0+",
                "license": "/index.php/Special:Version/License/CheckUser"
            }
        ],
        "fileextensions": [
            {
                "ext": "png"
            },
            {
                "ext": "gif"
            },
            {
                "ext": "jpg"
            },
            {
                "ext": "jpeg"
            }
        ],
        "rightsinfo": {
            "url": "",
            "text": "GNU Free Documentation License 1.3 or later"
        },
        "restrictions": {
            "types": [
                "create",
                "edit",
                "move",
                "upload"
            ],
            "levels": [
                "",
                "autoconfirmed",
                "sysop"
            ],
            "cascadinglevels": [
                "sysop"
            ],
            "semiprotectedlevels": [
                "autoconfirmed"
            ]
        },
        "skins": [
            {
                "code": "archlinux",
                "default": "",
                "*": "ArchLinux"
            },
            {
                "code": "fallback",
                "unusable": "",
                "*": "Fallback"
            },
            {
                "code": "apioutput",
                "unusable": "",
                "*": "ApiOutput"
            }
        ],
        "extensiontags": [
            "<pre>",
            "<nowiki>",
            "<gallery>",
            "<indicator>"
        ],
        "protocols": [
            "bitcoin:",
            "ftp://",
            "ftps://",
            "geo:",
            "git://",
            "gopher://",
            "http://",
            "https://",
            "irc://",
            "ircs://",
            "magnet:",
            "mailto:",
            "mms://",
            "news:",
            "nntp://",
            "redis://",
            "sftp://",
            "sip:",
            "sips:",
            "sms:",
            "ssh://",
            "svn://",
            "tel:",
            "telnet://",
            "urn:",
            "worldwind://",
            "xmpp:",
            "//"
        ],
        "defaultoptions": {
            "ccmeonemails": 0,
            "cols": 80,
            "date": "default",
            "diffonly": 0,
            "disablemail": 0,
            "editfont": "default",
            "editondblclick": 0,
            "editsectiononrightclick": 0,
            "enotifminoredits": 0,
            "enotifrevealaddr": 0,
            "enotifusertalkpages": 1,
            "enotifwatchlistpages": 1,
            "extendwatchlist": 1,
            "fancysig": 0,
            "forceeditsummary": 0,
            "gender": "unknown",
            "hideminor": 0,
            "hidepatrolled": 0,
            "imagesize": 2,
            "math": 1,
            "minordefault": 0,
            "newpageshidepatrolled": 0,
            "nickname": "",
            "norollbackdiff": 0,
            "numberheadings": 0,
            "previewonfirst": 0,
            "previewontop": 1,
            "rcdays": 7,
            "rclimit": 50,
            "rows": 25,
            "showhiddencats": 0,
            "shownumberswatching": 1,
            "showtoolbar": 1,
            "skin": "archlinux",
            "stubthreshold": 0,
            "thumbsize": 5,
            "underline": 2,
            "uselivepreview": 0,
            "usenewrc": 1,
            "watchcreations": 1,
            "watchdefault": 1,
            "watchdeletion": 0,
            "watchlistdays": 3,
            "watchlisthideanons": 0,
            "watchlisthidebots": 0,
            "watchlisthideliu": 0,
            "watchlisthideminor": 0,
            "watchlisthideown": 0,
            "watchlisthidepatrolled": 0,
            "watchmoves": 0,
            "watchrollback": 0,
            "wllimit": 250,
            "useeditwarning": 1,
            "prefershttps": 1,
            "language": "en",
            "variant-gan": "gan",
            "variant-iu": "iu",
            "variant-kk": "kk",
            "variant-ku": "ku",
            "variant-shi": "shi",
            "variant-sr": "sr",
            "variant-tg": "tg",
            "variant-uz": "uz",
            "variant-zh": "zh",
            "searchNs0": True,
            "searchNs1": False,
            "searchNs2": False,
            "searchNs3": False,
            "searchNs4": False,
            "searchNs5": False,
            "searchNs6": False,
            "searchNs7": False,
            "searchNs8": False,
            "searchNs9": False,
            "searchNs10": False,
            "searchNs11": False,
            "searchNs12": False,
            "searchNs13": False,
            "searchNs14": False,
            "searchNs15": False
        },
    }

    def test_coverage(self):
        paraminfo = fixtures.api.call_api(action="paraminfo", modules="query+siteinfo")
        properties = set(paraminfo["modules"][0]["parameters"][0]["type"])
        assert_equals(properties, fixtures.api.site.properties)

    def test_props(self):
        fixtures.api.site.fetch(list(self.props_data))
        def tester(propname, expected):
            assert_equals(getattr(fixtures.api.site, propname), expected)
        for propname, expected in self.props_data.items():
            yield tester, propname, expected

    @raises(AttributeError)
    def test_invalid(self):
        fixtures.api.site.invalid_property

    def test_interwikimap(self):
        expected = set(['ar', 'arxiv', 'bg', 'commons', 'cs', 'da', 'de', 'debian', 'doi', 'el', 'emacswiki', 'en', 'es', 'fa', 'fi', 'foldoc', 'fr', 'freebsdman', 'funtoo', 'gentoo', 'gregswiki', 'he', 'hr', 'hu', 'id', 'it', 'ja', 'ko', 'linuxwiki', 'lqwiki', 'lt', 'meta', 'metawikimedia', 'mozillawiki', 'mw', 'nl', 'phab', 'phabricator', 'pl', 'pt', 'rfc', 'ro', 'ru', 'sk', 'sourceforge', 'sr', 'sv', 'th', 'tr', 'uk', 'w', 'wikia', 'wikibooks', 'wikimedia', 'wikinews', 'wikipedia', 'wikiquote', 'wikisource', 'wikispecies', 'wikiversity', 'wikivoyage', 'wikt', 'wiktionary', 'wmf', 'zh-cn', 'zh-tw'])
        assert_equals(set(fixtures.api.site.interwikimap), expected)

    def test_interlanguagemap(self):
        external_tags = ["de", "fa", "fi", "fr", "ja", "ro", "sv", "tr"]
        internal_tags = ["ar", "bg", "cs", "da", "el", "en", "es", "he", "hr", "hu", "id", "it", "ko", "lt", "nl", "pl", "pt", "ru", "sk", "sr", "th", "uk", "zh-cn", "zh-tw"]
        expected = set(external_tags + internal_tags)
        assert_equals(set(fixtures.api.site.interlanguagemap), expected)

    def test_namespaces(self):
        expected = {0: '', 1: 'Talk', 2: 'User', 3: 'User talk', 4: 'ArchWiki', 5: 'ArchWiki talk', 6: 'File', 7: 'File talk', 8: 'MediaWiki', 9: 'MediaWiki talk', 10: 'Template', 11: 'Template talk', 12: 'Help', 13: 'Help talk', 14: 'Category', 15: 'Category talk', -1: 'Special', -2: 'Media'}
        assert_equals(fixtures.api.site.namespaces, expected)

