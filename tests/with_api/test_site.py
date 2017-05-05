#! /usr/bin/env python3

import pytest

from ws.client.api import LoginFailed

# TODO: pytest attribute
#@attr(speed="slow")
class test_site:
    """
    Tests intended mostly for detecting changes in the ArchWiki configuration.
    """

    props_data = {
	"general": {
            "mainpage": "Main page",
            "base": "https://wiki.archlinux.org/index.php/Main_page",
            "sitename": "ArchWiki",
            "logo": "https://wiki.archlinux.org/skins/archlinux/archlogo.png",
            "generator": "MediaWiki 1.28.2",
            "phpversion": "7.1.4",
            "phpsapi": "fpm-fcgi",
            "dbtype": "mysql",
            "dbversion": "5.7.17-13-log",
            "imagewhitelistenabled": "",
            "langconversion": "",
            "titleconversion": "",
            "linkprefixcharset": "",
            "linkprefix": "",
            "linktrail": "/^([a-z]+)(.*)$/sD",
            "legaltitlechars": " %!\"$&'()*,\\-.\\/0-9:;=?@A-Z\\\\^_`a-z~\\x80-\\xFF+",
            "invalidusernamechars": "@:",
            "case": "first-letter",
            "allcentralidlookupproviders": ["local"],
            "centralidlookupprovider": "local",
            "lang": "en",
            "fallback": [],
            "fallback8bitEncoding": "windows-1252",
            "fixarabicunicode": "",
            "fixmalayalamunicode": "",
            "writeapi": "",
            "timezone": "UTC",
            "timeoffset": 0,
            "articlepath": "/index.php/$1",
            "scriptpath": "",
            "script": "/index.php",
            "variantarticlepath": False,
            "server": "https://wiki.archlinux.org",
            "servername": "wiki.archlinux.org",
            "wikiid": "archwiki",
            "maxarticlesize": 2097152,
            "magiclinks": [],
            "interwikimagic": "",
            "uploadsenabled": "",
            "maxuploadsize": 104857600,
            "minuploadchunksize": 1024,
            "thumblimits": [
                120,
                150,
                180,
                200,
                250,
                300
            ],
            "imagelimits": [
                {
                    "width": 320,
                    "height": 240
                },
                {
                    "width": 640,
                    "height": 480
                },
                {
                    "width": 800,
                    "height": 600
                },
                {
                    "width": 1024,
                    "height": 768
                },
                {
                    "width": 1280,
                    "height": 1024
                }
            ],
            "favicon": "https://wiki.archlinux.org/favicon.ico"
        },
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
                    "changetags",
                    "editcontentmodel",
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
                    "deletechangetags",
                    "deleterevision",
                    "writeapi",
                    "abusefilter-modify",
                    "abusefilter-private",
                    "abusefilter-modify-restricted",
                    "abusefilter-revert",
                    "checkuser",
                    "checkuser-log",
                    "interwiki",
                    "nuke",
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
                "version": "2.4"
            },
            {
                "type": "other",
                "name": "MobileFrontend",
                "descriptionmsg": "mobile-frontend-desc",
                "author": "Patrick Reilly, Max Semenik, Jon Robson, Arthur Richards, Brion Vibber, Juliusz Gonera, Ryan Kaldari, Florian Schmidt, Rob Moen, Sam Smith",
                "url": "https://www.mediawiki.org/wiki/Extension:MobileFrontend",
                "version": "1.0.0",
                "license-name": "GPL-2.0+",
                "license": "/index.php/Special:Version/License/MobileFrontend",
                "credits": "/index.php/Special:Version/Credits/MobileFrontend"
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
            },
            {
                "type": "specialpage",
                "name": "Interwiki",
                "descriptionmsg": "interwiki-desc",
                "author": "Stephanie Amanda Stevens, Alexandre Emsenhuber, Robin Pepermans, Siebrand Mazeland, Platonides, Raimond Spekking, Sam Reed, Jack Phoenix, Calimonius the Estrange, ...",
                "url": "https://www.mediawiki.org/wiki/Extension:Interwiki",
                "version": "3.1 20160307",
                "license-name": "GPL-2.0+",
                "license": "/index.php/Special:Version/License/Interwiki"
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
                "type": "parserhook",
                "name": "ParserFunctions",
                "descriptionmsg": "pfunc_desc",
                "author": "Tim Starling, Robert Rohde, Ross McClure, Juraj Simlovic",
                "url": "https://www.mediawiki.org/wiki/Extension:ParserFunctions",
                "version": "1.6.0",
                "license-name": "GPL-2.0",
                "license": "/index.php/Special:Version/License/ParserFunctions"
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
            },
            {
                "ext": "webp"
            },
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
                "code": "minerva",
                "*": "Minerva"
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
            "forceeditsummary": 1,
            "gender": "unknown",
            "hideminor": 0,
            "hidecategorization": 1,    # MW 1.28
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
            "timecorrection": "System|0",   # MW 1.28
            "underline": 2,
            "uselivepreview": 0,
            "usenewrc": 1,
            "watchcreations": 1,
            "watchdefault": 1,
            "watchdeletion": 0,
            "watchlistdays": 3,
            "watchlisthideanons": 0,
            "watchlisthidebots": 0,
            "watchlisthidecategorization": 1,   # MW 1.28
            "watchlisthideliu": 0,
            "watchlisthideminor": 0,
            "watchlisthideown": 0,
            "watchlisthidepatrolled": 0,
            "watchlistreloadautomatically": 0,  # MW 1.28
            "watchmoves": 0,
            "watchrollback": 0,
            "watchuploads": 1,  # MW 1.28
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
        },
        "namespaces": {
            -2: {'*': 'Media', 'canonical': 'Media', 'case': 'first-letter', 'id': -2},
	    -1: {'*': 'Special', 'canonical': 'Special', 'case': 'first-letter', 'id': -1},
	    0: {'*': '',
                'case': 'first-letter',
                'content': '',
                'id': 0,
                'subpages': ''},
	    1: {'*': 'Talk',
	        'canonical': 'Talk',
	        'case': 'first-letter',
	        'id': 1,
	        'subpages': ''},
	    2: {'*': 'User',
	        'canonical': 'User',
	        'case': 'first-letter',
	        'id': 2,
	        'subpages': ''},
	    3: {'*': 'User talk',
	        'canonical': 'User talk',
	        'case': 'first-letter',
	        'id': 3,
	        'subpages': ''},
	    4: {'*': 'ArchWiki',
	        'canonical': 'Project',
	        'case': 'first-letter',
	        'id': 4,
	        'subpages': ''},
	    5: {'*': 'ArchWiki talk',
	        'canonical': 'Project talk',
	        'case': 'first-letter',
	        'id': 5,
	        'subpages': ''},
	    6: {'*': 'File', 'canonical': 'File', 'case': 'first-letter', 'id': 6},
	    7: {'*': 'File talk',
	        'canonical': 'File talk',
	        'case': 'first-letter',
	        'id': 7,
	        'subpages': ''},
	    8: {'*': 'MediaWiki',
	        'canonical': 'MediaWiki',
	        'case': 'first-letter',
	        'id': 8,
	        'subpages': ''},
	    9: {'*': 'MediaWiki talk',
	        'canonical': 'MediaWiki talk',
	        'case': 'first-letter',
	        'id': 9,
	        'subpages': ''},
	    10: {'*': 'Template',
	         'canonical': 'Template',
	         'case': 'first-letter',
	         'id': 10},
	    11: {'*': 'Template talk',
	         'canonical': 'Template talk',
	         'case': 'first-letter',
	         'id': 11,
	         'subpages': ''},
	    12: {'*': 'Help',
	         'canonical': 'Help',
	         'case': 'first-letter',
	         'id': 12,
	         'subpages': ''},
	    13: {'*': 'Help talk',
	         'canonical': 'Help talk',
	         'case': 'first-letter',
	         'id': 13,
	         'subpages': ''},
	    14: {'*': 'Category',
	         'canonical': 'Category',
	         'case': 'first-letter',
	         'id': 14},
	    15: {'*': 'Category talk',
	         'canonical': 'Category talk',
	         'case': 'first-letter',
	         'id': 15,
	         'subpages': ''}
	},
	"interwikimap": {
            'ar': {'language': 'العربية',
	           'local': '',
	           'prefix': 'ar',
	           'url': 'https://wiki.archlinux.org/index.php/$1_(%D8%A7%D9%84%D8%B9%D8%B1%D8%A8%D9%8A%D8%A9)'},
	    'arxiv': {'prefix': 'arxiv', 'url': 'http://www.arxiv.org/abs/$1'},
	    'bg': {'language': 'български',
	           'local': '',
	           'prefix': 'bg',
	           'url': 'https://wiki.archlinux.org/index.php/$1_(%D0%91%D1%8A%D0%BB%D0%B3%D0%B0%D1%80%D1%81%D0%BA%D0%B8)'},
	    'commons': {'api': 'https://commons.wikimedia.org/w/api.php',
	                'prefix': 'commons',
	                'url': 'https://commons.wikimedia.org/wiki/$1'},
	    'cs': {'language': 'čeština',
	           'local': '',
	           'prefix': 'cs',
	           'url': 'https://wiki.archlinux.org/index.php/$1_(%C4%8Cesky)'},
	    'da': {'language': 'dansk',
	           'local': '',
	           'prefix': 'da',
	           'url': 'https://wiki.archlinux.org/index.php/$1_(Dansk)'},
	    'de': {'language': 'Deutsch',
	           'local': '',
	           'prefix': 'de',
	           'url': 'https://wiki.archlinux.de/title/$1'},
	    'debian': {'prefix': 'debian', 'url': 'https://wiki.debian.org/$1'},
	    'doi': {'prefix': 'doi', 'url': 'http://dx.doi.org/$1'},
	    'el': {'language': 'Ελληνικά',
	           'local': '',
	           'prefix': 'el',
	           'url': 'https://wiki.archlinux.org/index.php/$1_(%CE%95%CE%BB%CE%BB%CE%B7%CE%BD%CE%B9%CE%BA%CE%AC)'},
	    'emacswiki': {'prefix': 'emacswiki',
	                  'url': 'http://www.emacswiki.org/cgi-bin/wiki.pl?$1'},
	    'en': {'language': 'English',
	           'local': '',
	           'prefix': 'en',
	           'url': 'https://wiki.archlinux.org/index.php/$1'},
	    'es': {'language': 'español',
	           'local': '',
	           'prefix': 'es',
	           'url': 'https://wiki.archlinux.org/index.php/$1_(Espa%C3%B1ol)'},
	    'fa': {'language': 'فارسی',
	           'local': '',
	           'prefix': 'fa',
	           'url': 'http://wiki.archusers.ir/index.php/$1'},
	    'fi': {'language': 'suomi',
	           'local': '',
	           'prefix': 'fi',
	           'url': 'https://wiki.archlinux.org/index.php/$1_(Suomi)'},
	    'foldoc': {'prefix': 'foldoc', 'url': 'http://foldoc.org/?$1'},
	    'fr': {'language': 'français',
	           'local': '',
	           'prefix': 'fr',
	           'url': 'http://wiki.archlinux.fr/$1'},
	    'freebsdman': {'prefix': 'freebsdman',
	                   'url': 'http://www.freebsd.org/cgi/man.cgi?query=$1'},
	    'funtoo': {'api': 'http://www.funtoo.org/api.php',
	               'prefix': 'funtoo',
	               'url': 'http://www.funtoo.org/$1'},
	    'gentoo': {'api': 'https://wiki.gentoo.org/api.php',
	               'prefix': 'gentoo',
	               'url': 'https://wiki.gentoo.org/wiki/$1'},
	    'gregswiki': {'prefix': 'gregswiki', 'url': 'http://mywiki.wooledge.org/$1'},
	    'he': {'language': 'עברית',
	           'local': '',
	           'prefix': 'he',
	           'url': 'https://wiki.archlinux.org/index.php/$1_(%D7%A2%D7%91%D7%A8%D7%99%D7%AA)'},
	    'hr': {'language': 'hrvatski',
	           'local': '',
	           'prefix': 'hr',
	           'url': 'https://wiki.archlinux.org/index.php/$1_(Hrvatski)'},
	    'hu': {'language': 'magyar',
	           'local': '',
	           'prefix': 'hu',
	           'url': 'https://wiki.archlinux.org/index.php/$1_(Magyar)'},
	    'id': {'language': 'Bahasa Indonesia',
	           'local': '',
	           'prefix': 'id',
	           'url': 'https://wiki.archlinux.org/index.php/$1_(Indonesia)'},
	    'it': {'language': 'italiano',
	           'local': '',
	           'prefix': 'it',
	           'url': 'https://wiki.archlinux.org/index.php/$1_(Italiano)'},
	    'ja': {'language': '日本語',
	           'local': '',
	           'prefix': 'ja',
	           'url': 'https://wiki.archlinuxjp.org/index.php/$1'},
	    'ko': {'language': '한국어',
	           'local': '',
	           'prefix': 'ko',
	           'url': 'https://wiki.archlinux.org/index.php/$1_(%ED%95%9C%EA%B5%AD%EC%96%B4)'},
	    'linuxwiki': {'prefix': 'linuxwiki', 'url': 'http://linuxwiki.de/$1'},
	    'lqwiki': {'prefix': 'lqwiki',
	               'url': 'http://wiki.linuxquestions.org/wiki/$1'},
	    'lt': {'language': 'lietuvių',
	           'local': '',
	           'prefix': 'lt',
	           'url': 'https://wiki.archlinux.org/index.php/$1_(Lietuvi%C5%A1kai)'},
	    'meta': {'api': 'https://meta.wikimedia.org/w/api.php',
	             'prefix': 'meta',
	             'url': 'https://meta.wikimedia.org/wiki/$1'},
	    'metawikimedia': {'api': 'https://meta.wikimedia.org/w/api.php',
	                      'prefix': 'metawikimedia',
	                      'url': 'https://meta.wikimedia.org/wiki/$1'},
	    'mozillawiki': {'api': 'https://wiki.mozilla.org/api.php',
	                    'prefix': 'mozillawiki',
	                    'url': 'http://wiki.mozilla.org/$1'},
	    'mw': {'api': 'https://www.mediawiki.org/w/api.php',
	           'prefix': 'mw',
	           'url': 'https://www.mediawiki.org/wiki/$1'},
	    'nl': {'language': 'Nederlands',
	           'local': '',
	           'prefix': 'nl',
	           'url': 'https://wiki.archlinux.org/index.php/$1_(Nederlands)'},
	    'phab': {'prefix': 'phab', 'url': 'https://phabricator.wikimedia.org/$1'},
	    'phabricator': {'prefix': 'phabricator',
	                    'url': 'https://phabricator.wikimedia.org/$1'},
	    'pl': {'language': 'polski',
	           'local': '',
	           'prefix': 'pl',
	           'url': 'https://wiki.archlinux.org/index.php/$1_(Polski)'},
            'pmid': {'prefix': 'pmid', 'url': 'https://www.ncbi.nlm.nih.gov/pubmed/$1?dopt=Abstract'},
	    'pt': {'language': 'português',
	           'local': '',
	           'prefix': 'pt',
	           'url': 'https://wiki.archlinux.org/index.php/$1_(Portugu%C3%AAs)'},
            'rfc': {'prefix': 'rfc', 'url': 'https://tools.ietf.org/html/rfc$1'},
	    'ro': {'language': 'română',
	           'local': '',
	           'prefix': 'ro',
	           'url': 'http://wiki.archlinux.ro/index.php/$1'},
	    'ru': {'language': 'русский',
	           'local': '',
	           'prefix': 'ru',
	           'url': 'https://wiki.archlinux.org/index.php/$1_(%D0%A0%D1%83%D1%81%D1%81%D0%BA%D0%B8%D0%B9)'},
	    'sk': {'language': 'slovenčina',
	           'local': '',
	           'prefix': 'sk',
	           'url': 'https://wiki.archlinux.org/index.php/$1_(Slovensk%C3%BD)'},
	    'sourceforge': {'prefix': 'sourceforge', 'url': 'http://sourceforge.net/$1'},
	    'sr': {'language': 'српски / srpski',
	           'local': '',
	           'prefix': 'sr',
	           'url': 'https://wiki.archlinux.org/index.php/$1_(%D0%A1%D1%80%D0%BF%D1%81%D0%BA%D0%B8)'},
	    'sv': {'language': 'svenska',
	           'local': '',
	           'prefix': 'sv',
	           'url': 'https://wiki.archlinux.org/index.php/$1_(Svenska)'},
	    'th': {'language': 'ไทย',
	           'local': '',
	           'prefix': 'th',
	           'url': 'https://wiki.archlinux.org/index.php/$1_(%E0%B9%84%E0%B8%97%E0%B8%A2)'},
	    'tr': {'language': 'Türkçe',
	           'local': '',
	           'prefix': 'tr',
	           'url': 'https://wiki.archlinux.org/index.php/$1_(T%C3%BCrk%C3%A7e)'},
	    'uk': {'language': 'українська',
	           'local': '',
	           'prefix': 'uk',
	           'url': 'https://wiki.archlinux.org/index.php/$1_(%D0%A3%D0%BA%D1%80%D0%B0%D1%97%D0%BD%D1%81%D1%8C%D0%BA%D0%B0)'},
	    'w': {'api': 'https://en.wikipedia.org/w/api.php',
	          'prefix': 'w',
	          'url': 'https://en.wikipedia.org/wiki/$1'},
	    'wikia': {'prefix': 'wikia', 'url': 'http://www.wikia.com/wiki/$1'},
	    'wikibooks': {'api': 'https://en.wikibooks.org/w/api.php',
	                  'prefix': 'wikibooks',
	                  'url': 'https://en.wikibooks.org/wiki/$1'},
	    'wikimedia': {'api': 'https://wikimediafoundation.org/w/api.php',
	                  'prefix': 'wikimedia',
	                  'url': 'https://wikimediafoundation.org/wiki/$1'},
	    'wikinews': {'api': 'https://en.wikinews.org/w/api.php',
	                 'prefix': 'wikinews',
	                 'url': 'https://en.wikinews.org/wiki/$1'},
	    'wikipedia': {'api': 'https://en.wikipedia.org/w/api.php',
	                  'prefix': 'wikipedia',
	                  'url': 'https://en.wikipedia.org/wiki/$1'},
	    'wikiquote': {'api': 'https://en.wikiquote.org/w/api.php',
	                  'prefix': 'wikiquote',
	                  'url': 'https://en.wikiquote.org/wiki/$1'},
	    'wikisource': {'api': 'https://wikisource.org/w/api.php',
	                   'prefix': 'wikisource',
	                   'url': 'https://wikisource.org/wiki/$1'},
	    'wikispecies': {'api': 'https://species.wikimedia.org/w/api.php',
	                    'prefix': 'wikispecies',
	                    'url': 'https://species.wikimedia.org/wiki/$1'},
	    'wikiversity': {'api': 'https://en.wikiversity.org/w/api.php',
	                    'prefix': 'wikiversity',
	                    'url': 'https://en.wikiversity.org/wiki/$1'},
	    'wikivoyage': {'api': 'https://en.wikivoyage.org/w/api.php',
	                   'prefix': 'wikivoyage',
	                   'url': 'https://en.wikivoyage.org/wiki/$1'},
	    'wikt': {'api': 'https://en.wiktionary.org/w/api.php',
	             'prefix': 'wikt',
	             'url': 'https://en.wiktionary.org/wiki/$1'},
	    'wiktionary': {'api': 'https://en.wiktionary.org/w/api.php',
	                   'prefix': 'wiktionary',
	                   'url': 'https://en.wiktionary.org/wiki/$1'},
	    'wmf': {'api': 'https://wikimediafoundation.org/w/api.php',
	            'prefix': 'wmf',
	            'url': 'https://wikimediafoundation.org/wiki/$1'},
	    'zh-hans': {'language': '中文（简体）\u200e',
	                'local': '',
	                'prefix': 'zh-hans',
	                'url': 'https://wiki.archlinux.org/index.php/$1_(%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87)'},
	    'zh-hant': {'language': '中文（繁體）\u200e',
	                'local': '',
	                'prefix': 'zh-hant',
	                'url': 'https://wiki.archlinux.org/index.php/$1_(%E6%AD%A3%E9%AB%94%E4%B8%AD%E6%96%87)'}
	},
    }

    def test_coverage(self, api):
        paraminfo = api.call_api(action="paraminfo", modules="query+siteinfo")
        properties = set(paraminfo["modules"][0]["parameters"][0]["type"])
        assert properties == api.site.properties

    @pytest.fixture(scope="class")
    def api(self, api):
        api.site.fetch(list(self.props_data))
        return api

    @pytest.mark.parametrize("propname, expected", props_data.items())
    def test_props(self, api, propname, expected):
        prop = getattr(api.site, propname).copy()
        # FIXME: ugly hack...
        if isinstance(prop, dict) and "time" in prop:
            del prop["time"]
        if propname == "general":
            if "git-branch" in prop:
                del prop["git-branch"]
            if "git-hash" in prop:
                del prop["git-hash"]
        assert prop == expected

    def test_invalid(self, api):
        with pytest.raises(AttributeError):
            api.site.invalid_property

    def test_interlanguagemap(self, api):
        external_tags = ["de", "fa", "fi", "fr", "ja", "ro", "sv", "tr"]
        internal_tags = ["ar", "bg", "cs", "da", "el", "en", "es", "he", "hr", "hu", "id", "it", "ko", "lt", "nl", "pl", "pt", "ru", "sk", "sr", "th", "uk", "zh-hans", "zh-hant"]
        expected = set(external_tags + internal_tags)
        assert set(api.site.interlanguagemap) == expected
