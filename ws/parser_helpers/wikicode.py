#! /usr/bin/env python3

import re

import mwparserfromhell

from .encodings import dotencode

__all__ = ["strip_markup", "get_adjacent_node", "get_parent_wikicode", "remove_and_squash", "get_section_headings", "get_anchors", "ensure_flagged_by_template", "ensure_unflagged_by_template"]

def strip_markup(text, normalize=True, collapse=True):
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
            return None
        try:
            node = parent.get(index)
            # don't EVER remove whitespace from non-Text nodes (it would
            # modify the objects by converting to str, making the operation
            # and replacing the object with str, but we keep references to
            # the old nodes)
            if not isinstance(node, mwparserfromhell.nodes.text.Text):
                return None
            return node
        except IndexError:
            return None

    prev = _get_text(index - 1)
    next_ = _get_text(index)

    if prev is None and next_ is not None:
        next_.value = next_.lstrip()
    elif prev is not None and next_ is None:
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
    matches = re.findall(r"^((\={1,6})\s*)([^\n]*?)(\s*(\2))$", text, flags=re.MULTILINE | re.DOTALL)
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

def ensure_flagged_by_template(wikicode, node, template_name, *template_parameters):
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
        wikicode.replace(adjacent, flag)
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
