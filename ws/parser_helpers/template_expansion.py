#! /usr/bin/env python3

import logging

import mwparserfromhell

from . import encodings
from .title import Title, TitleError
from .wikicode import parented_ifilter

logger = logging.getLogger(__name__)

__all__ = [
    "MagicWords", "prepare_content_for_rendering", "prepare_template_for_transclusion",
    "expand_templates",
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

    def __init__(self, src_title):
        self.src_title = src_title

    @classmethod
    def is_magic_word(klass, name):
        if name in klass.VARIABLES:
            return True
        if ":" in name:
            prefix = name.split(":")[0]
            if prefix in klass.VARIABLES_COLON or prefix.lower() in klass.PARSER_FUNCTIONS:
                return True
        return False

    def get_replacement(self, magic):
        name = str(magic.name).strip()

        if name == "FULLPAGENAME":
            return self.src_title.fullpagename
        elif name == "PAGENAME":
            return self.src_title.pagename
        elif name == "BASEPAGENAME":
            return self.src_title.basepagename
        elif name == "SUBPAGENAME":
            return self.src_title.subpagename
        elif name == "SUBJECTPAGENAME" or name == "ARTICLEPAGENAME":
            return self.src_title.articlepagename
        elif name == "TALKPAGENAME":
            return self.src_title.talkpagename
        elif name == "ROOTPAGENAME":
            return self.src_title.rootpagename

        elif ":" in name:
            prefix, arg = name.split(":", maxsplit=1)
            prefix = prefix.lower()

            if prefix == "urlencode":
                return encodings.urlencode(arg)
            elif prefix == "anchorencode":
                return encodings.dotencode(arg)
            elif prefix == "#if":
                try:
                    if arg.strip():
                        return magic.get(1).value.strip()
                    else:
                        return magic.get(2).value.strip()
                except ValueError:
                    return ""
            elif prefix == "#switch":
                # MW incompatibility: fall-thgourh cases are not supported
                try:
                    replacement = magic.get(str(arg).strip()).value
                except ValueError:
                    try:
                        replacement = magic.get("#default").value
                    except ValueError:
                        try:
                            replacement = magic.get(1).value
                        except ValueError:
                            replacement = ""
                return replacement.strip()

def prepare_content_for_rendering(wikicode):
    """
    Prepare the wikicode of a page for `rendering`.

    I.e. do the same wikicode transformations that MediaWiki does before
    rendering a page:

    - the `partial transclusion`_ tags ``<noinclude>``, ``<includeonly>``
      and ``<onlyinclude>`` are handled so that only content inside the
      ``<noinclude>`` or ``<onlyinclude>`` tags remains

    :param wikicode: the wikicode of the template
    :returns: ``None``, the wikicode is modified in place.

    .. _`partial transclusion`: https://www.mediawiki.org/wiki/Transclusion#Partial_transclusion
    """
    for tag in wikicode.ifilter_tags(recursive=True):
        # drop all <includeonly> tags and everything inside
        if tag.tag == "includeonly":
            try:
                wikicode.remove(tag)
            except ValueError:
                # this may happen for nested tags which were previously removed/replaced
                pass
        # drop <noinclude> and <onlyinclude> tags, but nothing outside or inside
        elif tag.tag == "noinclude" or tag.tag == "onlyinclude":
            try:
                wikicode.replace(tag, tag.contents)
            except ValueError:
                # this may happen for nested tags which were previously removed/replaced
                pass

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
                     substitute_magic_words=True):
    """
    Recursively expands all templates on a MediaWiki page.

    :param ws.parser_helpers.title.Title title:
        The title of the page where the templates will be expanded. Used for
        infinite loop prevention and context (e.g. relative transclusions like
        ``{{/foo/bar}}``).
    :param wikicode:
        The content of the page where templates should be expanded, as a
        :py:class:`mwparserfromhell.wikicode.Wikicode` object.
    :param content_getter_func:
        A callback function which should return the content of a transcluded
        page. It is called as ``content_getter_func(title)``, where ``title``
        is the :py:class:`Title <ws.parser_helpers.title.Title>` object
        representing the title of the transcluded page. The function should
        raise :py:exc:`ValueError` if the requested page does not exist.
    :param bool substitute_magic_words:
        Whether to substitute `magic words`_. Note that only a couple of
        interesting/important cases are actually handled.
    :returns: ``None``, the wikicode is modified in place.

    .. _`magic words`: https://www.mediawiki.org/wiki/Help:Magic_words
    """
    if not isinstance(wikicode, mwparserfromhell.wikicode.Wikicode):
        raise TypeError("wikicode is of type {} instead of mwparserfromhell.wikicode.Wikicode".format(type(wikicode)))

    def get_target_title(src_title, title):
        target = Title(src_title.context, title)
        if title.startswith("/"):
            return target.make_absolute(src_title)
        elif target.leading_colon:
            return target
        elif target.namespacenumber == 0:
            # set the default transclusion namespace
            target.namespace = target.context.namespaces[10]["*"]
        return target

    def expand(title, wikicode, content_getter_func, visited_templates):
        """
        Adds infinite loop protection to the functionality declared by :py:func:`expand_templates`.
        """
#        for template in wikicode.ifilter_templates(recursive=wikicode.RECURSE_OTHERS):
        # performance optimization, see https://github.com/earwig/mwparserfromhell/issues/195
        for parent, template in parented_ifilter(wikicode, forcetype=mwparserfromhell.nodes.template.Template, recursive=wikicode.RECURSE_OTHERS):
            # handle cases like {{ {{foo}} | bar }} --> {{foo}} has to be substituted first
            expand(title, template.name, content_getter_func, visited_templates)

            name = str(template.name).strip()

            # handle transclusion modifiers: https://www.mediawiki.org/wiki/Help:Magic_words#Transclusion_modifiers
            # MW incompatibility: the int: modifier is not supported (it does some translation based on the content/user language)
            original_name = name
            if ":" in name:
                modifier, name = name.split(":", maxsplit=1)
                # strip modifiers which don't make a difference for template expansion
                if modifier.lower() in {"msgnw", "subst", "safesubst"}:
                    template.name = name
                # TODO: handle msg: and raw: (prefer a template, but fall back to magic word)
                else:
                    # unhandled modifier - restore the name
                    modifier = ""
                    name = original_name
            else:
                modifier = ""

            # handle magic words
            if MagicWords.is_magic_word(name):
                if substitute_magic_words is True:
                    # MW incompatibility: in some cases, MediaWiki tries to transclude a template
                    # if the parser function failed (e.g. "{{ns:Foo}}" -> "{{Template:Ns:Foo}}")
                    mw = MagicWords(title)
                    replacement = mw.get_replacement(template)
                    if replacement is not None:
                        # expand the replacement to handle nested magic words in parser functions like {{#if:}})
                        replacement = mwparserfromhell.parse(replacement)
                        expand(title, replacement, content_getter_func, visited_templates)
#                        wikicode.replace(template, replacement)
                        parent.replace(template, replacement, recursive=False)
            else:
                try:
                    target_title = get_target_title(title, name)
                except TitleError:
                    logger.error("Invalid transclusion on page [[{}]]: {}".format(title, template))
                    continue

                try:
                    content = content_getter_func(target_title)
                except ValueError:
                    if not modifier:
                        # If the target page does not exist, MediaWiki just skips the expansion,
                        # but it renders a wikilink to the non-existing page.
#                        wikicode.replace(template, "[[{}]]".format(target_title))
                        parent.replace(template, "[[{}]]".format(target_title), recursive=False)
                    else:
                        # Restore the modifier, but don't render a wikilink.
                        template.name = original_name
                    continue

                # Note:
                # MW has a special case when the first character produced by the template is one of ":;*#", MediaWiki inserts a linebreak
                # reference: https://en.wikipedia.org/wiki/Help:Template#Problems_and_workarounds
                # TODO: check what happens in our case
                content = mwparserfromhell.parse(content)
                prepare_template_for_transclusion(content, template)

                # expand only if the infinite loop checker does not kick in
                _key = str(template)
                if _key not in visited_templates:
                    visited_templates.add(_key)
                    expand(title, content, content_getter_func, visited_templates)
                    visited_templates.remove(_key)
                else:
                    # MediaWiki fallback message
                    content = "<span class=\"error\">Template loop detected: [[{}]]</span>".format(target_title)

#                wikicode.replace(template, content)
                parent.replace(template, content, recursive=False)

    prepare_content_for_rendering(wikicode)
    expand(title, wikicode, content_getter_func, set())
