#! /usr/bin/env python3

import mwparserfromhell

from .title import canonicalize

__all__ = [
    "prepare_template_for_transclusion", "expand_templates",
]

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

def expand_templates(title, wikicode, content_getter_func, *, template_prefix="Template"):
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
    :returns: ``None``, the wikicode is modified in place.
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
            name = canonicalize(str(template.name))
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
