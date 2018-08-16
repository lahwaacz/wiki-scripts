#! /usr/bin/env python3

import re

import mwparserfromhell

from .encodings import dotencode
from .title import canonicalize

__all__ = [
    "strip_markup", "get_adjacent_node", "get_parent_wikicode", "remove_and_squash",
    "get_section_headings", "get_anchors", "ensure_flagged_by_template",
    "ensure_unflagged_by_template", "prepare_template_for_transclusion", "expand_templates",
]

def strip_markup(text, normalize=True, collapse=True):
    """
    Parses the given text and returns the text after stripping all MediaWiki
    markup, leaving only the plain text.

    :param normalize: passed to :py:func:`mwparserfromhell.wikicode.Wikicode.strip_code`
    :param collapse: passed to :py:func:`mwparserfromhell.wikicode.Wikicode.strip_code`
    :returns: :py:obj:`str`
    """
    wikicode = mwparserfromhell.parse(text)
    return wikicode.strip_code(normalize, collapse)

def get_adjacent_node(wikicode, node, ignore_whitespace=False):
    """
    Get the node immediately following `node` in `wikicode`.

    :param wikicode: a :py:class:`mwparserfromhell.wikicode.Wikicode` object
    :param node: a :py:class:`mwparserfromhell.nodes.Node` object
    :param ignore_whitespace: When True, the whitespace between `node` and the
            node being returned is ignored, i.e. the returned object is
            guaranteed to not be an all white space text, but it can still be a
            text with leading space.
    :returns: a :py:class:`mwparserfromhell.nodes.Node` object or None if `node`
            is the last object in `wikicode`
    """
    i = wikicode.index(node) + 1
    try:
        n = wikicode.get(i)
        while ignore_whitespace and n.isspace():
            i += 1
            n = wikicode.get(i)
        return n
    except IndexError:
        return None

def get_parent_wikicode(wikicode, node):
    """
    Returns the parent of `node` as a `wikicode` object.
    Raises :exc:`ValueError` if `node` is not a descendant of `wikicode`.
    """
    context, index = wikicode._do_strong_search(node, True)
    return context

def remove_and_squash(wikicode, obj):
    """
    Remove `obj` from `wikicode` and fix whitespace in the place it was removed from.
    """
    parent = get_parent_wikicode(wikicode, obj)
    index = parent.index(obj)
    parent.remove(obj)

    def _get_text(index):
        # the first node has no previous node, especially not the last node
        if index < 0:
            return None, None
        try:
            node = parent.get(index)
            # don't EVER remove whitespace from non-Text nodes (it would
            # modify the objects by converting to str, making the operation
            # and replacing the object with str, but we keep references to
            # the old nodes)
            if not isinstance(node, mwparserfromhell.nodes.text.Text):
                return None, mwparserfromhell.nodes.text.Text
            return node, mwparserfromhell.nodes.text.Text
        except IndexError:
            return None, None

    prev, prev_cls = _get_text(index - 1)
    next_, next_cls = _get_text(index)

    if prev is None and next_ is not None:
        # strip only at the beginning of the document, not after non-text elements,
        # see https://github.com/lahwaacz/wiki-scripts/issues/44
        if prev_cls is None:
            next_.value = next_.lstrip()
    elif prev is not None and next_ is None:
        # strip only at the end of the document, not before non-text elements,
        # see https://github.com/lahwaacz/wiki-scripts/issues/44
        if next_cls is None:
            prev.value = prev.value.rstrip()
    elif prev is not None and next_ is not None:
        if prev.endswith(" ") and next_.startswith(" "):
            prev.value = prev.rstrip(" ")
            next_.value = " " + next_.lstrip(" ")
        elif prev.endswith("\n") and next_.startswith("\n"):
            if prev[:-1].endswith("\n") or next_[1:].startswith("\n"):
                # preserve preceding blank line
                prev.value = prev.rstrip("\n") + "\n\n"
                next_.value = next_.lstrip("\n")
            else:
                # leave one linebreak
                prev.value = prev.rstrip("\n") + "\n"
                next_.value = next_.lstrip("\n")
        elif prev.endswith("\n"):
            next_.value = next_.lstrip()
        elif next_.startswith("\n"):    # pragma: no branch
            prev.value = prev.rstrip()
        # merge successive Text nodes
        prev.value += next_.value
        parent.remove(next_)

def get_section_headings(text):
    """
    Extracts section headings from given text. Custom regular expression is used
    instead of :py:mod:`mwparserfromhell` for performance reasons.

    :param str text: content of the wiki page
    :returns: list of section headings (without the ``=`` marks)
    """
    # re.findall returns a list of tuples of the matched groups
    # gotcha: the line must start with '=', but does not have to end with '=' (trailing whitespace is ignored)
    matches = re.findall(r"^((\={1,6})[^\S\n]*)([^\n]+?)([^\S\n]*(\2))[^\S\n]*$", text, flags=re.MULTILINE | re.DOTALL)
    return [match[2] for match in matches]

def get_anchors(headings, pretty=False, suffix_sep="_"):
    """
    Converts section headings to anchors.

    .. note::
        Known issues:

        - templates are always fully stripped (doing this right requires
          template expansion)
        - all tags are always stripped, even invalid tags (``mwparserfromhell``
          is not that configurable)
        - if ``pretty`` is ``True``, tags escaped with <nowiki> in the input
          are not encoded in the output

    :param list headings:
        section headings (obtained e.g. with :py:func:`get_section_headings`)
    :param bool pretty:
        if ``True``, the anchors will be as pretty as possible (e.g. for use
        in wikilinks), otherwise they are fully dot-encoded
    :param str suffix_sep:
        the separator between the base anchor and numeric suffix for duplicate
        section names
    :returns: list of section anchors
    """
    # MediaWiki markup should be stripped, but the text has to be parsed as a
    # heading, otherwise e.g. starting '#' would be understood as a list and
    # stripped as well.
    anchors = [strip_markup("={}=".format(heading)) for heading in headings]
    if pretty is False:
        anchors = [dotencode(a) for a in anchors]
    else:
        # anchors can't contain '[', '|', ']' and tags encode them manually
        anchors = [a.replace("[", "%5B").replace("|", "%7C").replace("]", "%5D") for a in anchors]

    # handle equivalent headings duplicated on the page
    for i, anchor in enumerate(anchors):
        j = 2
        while anchor in anchors[:i]:
            anchor = anchors[i] + suffix_sep + "{}".format(j)
            j += 1
        # update the main array
        anchors[i] = anchor
    return anchors

def ensure_flagged_by_template(wikicode, node, template_name, *template_parameters, overwrite_parameters=True):
    """
    Makes sure that ``node`` in ``wikicode`` is immediately (except for
    whitespace) followed by a template with ``template_name`` and optional
    ``template_parameters``.

    :param wikicode: a :py:class:`mwparserfromhell.wikicode.Wikicode` object
    :param node: a :py:class:`mwparserfromhell.nodes.Node` object
    :param str template_name: the name of the template flag
    :param template_parameters: optional template parameters
    :returns: the template flag, as a
        :py:class:`mwparserfromhell.nodes.template.Template` objet
    """
    parent = get_parent_wikicode(wikicode, node)
    adjacent = get_adjacent_node(parent, node, ignore_whitespace=True)

    if template_parameters:
        flag = "{{%s}}" % "|".join([template_name, *template_parameters])
    else:
        flag = "{{%s}}" % template_name
    flag = mwparserfromhell.parse(flag).nodes[0]
    assert(isinstance(flag, mwparserfromhell.nodes.Template))

    if isinstance(adjacent, mwparserfromhell.nodes.Template) and adjacent.name.matches(template_name):
        # in case of {{Dead link}} we want to preserve the original parameters
        if overwrite_parameters is True:
            wikicode.replace(adjacent, flag)
        else:
            flag = adjacent
    else:
        wikicode.insert_after(node, flag)

    assert(get_parent_wikicode(wikicode, flag) is parent)
    return flag

def ensure_unflagged_by_template(wikicode, node, template_name):
    """
    Makes sure that ``node`` in ``wikicode`` is not immediately (except for
    whitespace) followed by a template with ``template_name``.

    :param wikicode: a :py:class:`mwparserfromhell.wikicode.Wikicode` object
    :param node: a :py:class:`mwparserfromhell.nodes.Node` object
    :param str template_name: the name of the template flag
    """
    parent = get_parent_wikicode(wikicode, node)
    adjacent = get_adjacent_node(parent, node, ignore_whitespace=True)

    if isinstance(adjacent, mwparserfromhell.nodes.Template) and adjacent.name.matches(template_name):
        remove_and_squash(wikicode, adjacent)

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
