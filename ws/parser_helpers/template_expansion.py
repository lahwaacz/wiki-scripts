#! /usr/bin/env python3

import mwparserfromhell

from . import encodings
from .title import canonicalize

__all__ = [
    "MagicWords", "prepare_template_for_transclusion", "expand_templates",
]

class MagicWords:
    """
    Class for handling `MediaWiki magic words`_.

    .. _`MediaWiki magic words`: https://www.mediawiki.org/wiki/Help:Magic_words
    """
    # variables (all must be uppercase)
    # reference: https://www.mediawiki.org/wiki/Help:Magic_words#Variables
    VARIABLES = {
        # date and time
        "CURRENTYEAR",
        "CURRENTMONTH",
        "CURRENTMONTH1",
        "CURRENTMONTHNAME",
        "CURRENTMONTHNAMEGEN",
        "CURRENTMONTHABBREV",
        "CURRENTDAY",
        "CURRENTDAY2",
        "CURRENTDOW",
        "CURRENTDAYNAME",
        "CURRENTTIME",
        "CURRENTHOUR",
        "CURRENTWEEK",
        "CURRENTTIMESTAMP",
        "LOCALYEAR",
        "LOCALMONTH",
        "LOCALMONTH1",
        "LOCALMONTHNAME",
        "LOCALMONTHNAMEGEN",
        "LOCALMONTHABBREV",
        "LOCALDAY",
        "LOCALDAY2",
        "LOCALDOW",
        "LOCALDAYNAME",
        "LOCALTIME",
        "LOCALHOUR",
        "LOCALWEEK",
        "LOCALTIMESTAMP",
        # technical metadata
        "SITENAME",
        "SERVER",
        "SERVERNAME",
        "DIRMARK",
        "DIRECTIONMARK",
        "SCRIPTPATH",
        "STYLEPATH",
        "CURRENTVERSION",
        "CONTENTLANGUAGE",
        "CONTENTLANG",
        ## page
        "PAGEID",
        "PAGELANGUAGE",
        "CASCADINGSOURCES",
        ## latest revision to current page
        "REVISIONID",
        "REVISIONDAY",
        "REVISIONDAY2",
        "REVISIONMONTH",
        "REVISIONMONTH1",
        "REVISIONYEAR",
        "REVISIONTIMESTAMP",
        "REVISIONUSER",
        "REVISIONSIZE",
        # statistics
        "NUMBEROFPAGES",
        "NUMBEROFARTICLES",
        "NUMBEROFFILES",
        "NUMBEROFEDITS",
        "NUMBEROFVIEWS",
        "NUMBEROFUSERS",
        "NUMBEROFADMINS",
        "NUMBEROFACTIVEUSERS",
        # page names
        "FULLPAGENAME",
        "PAGENAME",
        "BASEPAGENAME",
        "SUBPAGENAME",
        "SUBJECTPAGENAME",
        "ARTICLEPAGENAME",
        "TALKPAGENAME",
        "ROOTPAGENAME",
        "FULLPAGENAMEE",
        "PAGENAMEE",
        "BASEPAGENAMEE",
        "SUBPAGENAMEE",
        "SUBJECTPAGENAMEE",
        "ARTICLEPAGENAMEE",
        "TALKPAGENAMEE",
        "ROOTPAGENAMEE",
        # namespaces
        "NAMESPACENUMBER",
        "NAMESPACE",
        "SUBJECTSPACE",
        "ARTICLESPACE",
        "TALKSPACE",
        "NAMESPACEE",
        "SUBJECTSPACEE",
        "ARTICLESPACEE",
        "TALKSPACEE",
        # other
        "!",
    }

    # variables taking a parameter after ":" (all must be uppercase)
    VARIABLES_COLON = {
        # technical metadata
        ## page
        "PROTECTIONLEVEL",
        "PROTECTIONEXPIRY",
        ## affects page content
        "DISPLAYTITLE",
        "DEFAULTSORT",
        "DEFAULTSORTKEY",
        "DEFAULTCATEGORYSORT",
        # statistics
        "PAGESINCATEGORY",
        "PAGESINCAT",
        "NUMBERINGROUP",
        "NUMINGROUP",
        "PAGESINNS",
        "PAGESINNAMESPACE",
        # page names
        # (the parameter after colon is optional, so they are also in VARIABLES)
        "FULLPAGENAME",
        "PAGENAME",
        "BASEPAGENAME",
        "SUBPAGENAME",
        "SUBJECTPAGENAME",
        "ARTICLEPAGENAME",
        "TALKPAGENAME",
        "ROOTPAGENAME",
        "FULLPAGENAMEE",
        "PAGENAMEE",
        "BASEPAGENAMEE",
        "SUBPAGENAMEE",
        "SUBJECTPAGENAMEE",
        "ARTICLEPAGENAMEE",
        "TALKPAGENAMEE",
        "ROOTPAGENAMEE",
        # namespaces
        # (the parameter after colon is optional, so they are also in VARIABLES)
        "NAMESPACENUMBER",
        "NAMESPACE",
        "SUBJECTSPACE",
        "ARTICLESPACE",
        "TALKSPACE",
        "NAMESPACEE",
        "SUBJECTSPACEE",
        "ARTICLESPACEE",
        "TALKSPACEE",
        # technical metadata of another page
        # (classified as "parser functions" in MediaWiki, but they must be uppercase,
        # see https://www.mediawiki.org/wiki/Help:Magic_words#Technical_metadata_of_another_page )
        "PAGEID",
        "PAGESIZE",
        "CASCADINGSOURCES",
        "REVISIONID",
        "REVISIONDAY",
        "REVISIONDAY2",
        "REVISIONMONTH",
        "REVISIONMONTH1",
        "REVISIONYEAR",
        "REVISIONTIMESTAMP",
        "REVISIONUSER",
    }

    # parser functions (case-insensitive, all take a parameter after ":")
    # reference: https://www.mediawiki.org/wiki/Help:Magic_words#Parser_functions
    PARSER_FUNCTIONS = {
        # URL data
        "localurl",
        "fullurl",
        "canonicalurl",
        "filepath",
        "urlencode",
        "anchorencode",
        # namespaces
        "ns",
        "nse",
        # formatting
        "formatnum",
        "#dateformat",
        "#formatdate",
        "lc",
        "lcfirst",
        "uc",
        "ucfirst",
        "padleft",
        "padright",
        # localization
        "plural",
        "grammar",
        "gender",
        "int",
        # miscellaneous
        "#language",
        "#special",
        "#tag",
        # Extension:ParserFunctions
        # reference: https://www.mediawiki.org/wiki/Help:Extension:ParserFunctions
        "#expr",
        "#if",
        "#ifeq",
        "#iferror",
        "#ifexpr",
        "#ifexist",
        "#rel2abs",
        "#switch",
        "#time",
        "#timel",
        "#titleparts",
    }

    @classmethod
    def is_magic_word(klass, name):
        if name in klass.VARIABLES:
            return True
        if ":" in name:
            prefix = name.split(":")[0]
            if prefix in klass.VARIABLES_COLON or prefix.lower() in klass.PARSER_FUNCTIONS:
                return True
        return False

    @classmethod
    def substitute(klass, wikicode, magic):
        name = str(magic.name)
        if ":" in name:
            prefix, arg = name.split(":", maxsplit=1)
            prefix = prefix.lower()

            if prefix == "urlencode":
                wikicode.replace(magic, encodings.urlencode(arg))
            elif prefix == "anchorencode":
                wikicode.replace(magic, encodings.dotencode(arg))

def prepare_template_for_transclusion(wikicode, template):
    """
    Prepares the wikicode of a template for transclusion:

    - the `partial transclusion`_ tags ``<noinclude>``, ``<includeonly>``
      and ``<onlyinclude>`` are handled
    - template arguments (``{{{foo}}}`` etc.) are substituted with the supplied
      parameters as specified on the target page

    :param wikicode: the wikicode of the template
    :param template: the template object holding parameters for substitution
    :returns: ``None``, the wikicode is modified in place.

    .. _`partial transclusion`: https://www.mediawiki.org/wiki/Transclusion#Partial_transclusion
    """
    # pass 1: if there is an <onlyinclude> tag *anywhere*, even inside <noinclude>,
    #         discard anything but its content
    # FIXME: bug in mwparserfromhell: <onlyinclude> should be parsed even inside <nowiki> tags
    for tag in wikicode.ifilter_tags(recursive=True):
        if tag.tag == "onlyinclude":
            wikicode.nodes = tag.contents.nodes
            break

    # pass 2: handle <noinclude> and <includeonly> tags
    for tag in wikicode.ifilter_tags(recursive=True):
        # drop <noinclude> tags and everything inside
        if tag.tag == "noinclude":
            try:
                wikicode.remove(tag)
            except ValueError:
                # this may happen for nested tags which were previously removed/replaced
                pass
        # drop <includeonly> tags, but nothing outside or inside
        elif tag.tag == "includeonly":
            try:
                wikicode.replace(tag, tag.contents)
            except ValueError:
                # this may happen for nested tags which were previously removed/replaced
                pass

    # wrapper function with protection against infinite recursion
    def substitute(wikicode, template, substituted_args):
        for arg in wikicode.ifilter_arguments(recursive=wikicode.RECURSE_OTHERS):
            # handle nested substitution like {{{ {{{1}}} |foo }}}
            substitute(arg.name, template, substituted_args)
            try:
                param_value = template.get(arg.name).value
            except ValueError:
                param_value = arg.default
            # If a template contains e.g. {{{1}}} and no corresponding parameter is given,
            # MediaWiki renders "{{{1}}}" verbatim.
            if param_value is not None:
                # handle nested substitution like {{{a| {{{b| {{{c|}}} }}} }}}
                # watch out for infinite recursion when passing arguments, e.g. Template:A: {{B| {{{1}}} }}; Template:B: {{{1}}}
                str_arg = str(arg)
                if str_arg not in substituted_args:
                    substituted_args.add(str_arg)
                    substitute(param_value, template, substituted_args)
                    substituted_args.remove(str_arg)
                    wikicode.replace(arg, param_value)

    # substitute template arguments
    substitute(wikicode, template, set())

def expand_templates(title, wikicode, content_getter_func, *,
                     template_prefix="Template", substitute_magic_words=True):
    """
    Recursively expands all templates on a MediaWiki page.

    :param str title:
        The title of the page where the templates will be expanded. Used for
        infinite loop prevention and context (e.g. relative transclusions like
        ``{{/foo/bar}}``).
    :param wikicode:
        The content of the page where templates should be expanded, as a
        :py:class:`mwparserfromhell.wikicode.Wikicode` object.
    :param content_getter_func:
        A callback function which should return the content of a transcluded
        page. It is called as ``content_getter_func(name)``, where the string
        ``name`` is the canonical name of the transcluded page. For example,
        in ``{{ foo bar | baz }}``, the ``name`` is ``"Template:Foo bar"``. The
        function should raise :py:exc:`ValueError` if the requested page does
        not exist.
    :param str template_prefix:
        Localized prefix of the template namespace.
    :param bool substitute_magic_words:
        Whether to substitute `magic words`_. Note that only a couple of
        interesting/important cases are actually handled.
    :returns: ``None``, the wikicode is modified in place.

    .. _`magic words`: https://www.mediawiki.org/wiki/Help:Magic_words
    """
    if not isinstance(wikicode, mwparserfromhell.wikicode.Wikicode):
        raise TypeError("wikicode is of type {} instead of mwparserfromhell.wikicode.Wikicode".format(type(wikicode)))

    # TODO: this should be done in the Title class
    def handle_relative_title(src_title, title):
        nonlocal template_prefix
        if title.startswith("/"):
            return src_title + title
        elif title.startswith(":"):
            return canonicalize(title[1:])
        else:
            return template_prefix + ":" + canonicalize(title)

    def expand(title, wikicode, content_getter_func, visited_pages):
        """
        Adds infinite loop protection to the functionality declared by :py:func:`expand_templates`.
        """
        for template in wikicode.ifilter_templates(recursive=wikicode.RECURSE_OTHERS):
            # handle cases like {{ {{foo}} | bar }} --> {{foo}} has to be substituted first
            expand(title, template.name, content_getter_func, visited_pages)

            # handle magic words
            name = str(template.name)
            if MagicWords.is_magic_word(name):
                if substitute_magic_words is True:
                    MagicWords.substitute(wikicode, template)
                continue

            # TODO: handle transclusion modifiers: https://www.mediawiki.org/wiki/Help:Magic_words#Transclusion_modifiers

            name = canonicalize(name)
            target_title = canonicalize(handle_relative_title(title, name))

            try:
                content = content_getter_func(target_title)
            except ValueError:
                # If the target page does not exist, MediaWiki just skips the expansion,
                # but it renders a wikilink to the non-existing page.
                # TODO: the wikilink appears both in pagelinks and templatelinks tables !!!
                wikicode.replace(template, "[[{}]]".format(handle_relative_title(title, str(template.name))))
                continue

            # Note:
            # MW has a special case when the first character produced by the template is one of ":;*#", MediaWiki inserts a linebreak
            # reference: https://en.wikipedia.org/wiki/Help:Template#Problems_and_workarounds
            # TODO: check what happens in our case
            content = mwparserfromhell.parse(content)
            prepare_template_for_transclusion(content, template)

            # Expand only if the infinite loop checker does not kick in, otherwise we just leave it unexpanded.
            if target_title not in visited_pages:
                visited_pages.add(target_title)
                expand(title, content, content_getter_func, visited_pages)
                visited_pages.remove(target_title)

            wikicode.replace(template, content)

    title = canonicalize(title)
    expand(title, wikicode, content_getter_func, {title})
