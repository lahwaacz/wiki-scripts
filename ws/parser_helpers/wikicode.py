import re
from itertools import chain
from typing import Any, Callable, Generator, Iterable, cast

import mwparserfromhell
from mwparserfromhell.nodes import Node
from mwparserfromhell.wikicode import Wikicode

from .encodings import dotencode
from .title import canonicalize

__all__ = [
    "strip_markup",
    "get_adjacent_node",
    "get_parent_wikicode",
    "remove_and_squash",
    "get_section_headings",
    "get_anchors",
    "ensure_flagged_by_template",
    "ensure_unflagged_by_template",
    "is_flagged_by_template",
    "is_redirect",
    "parented_ifilter",
]


def strip_markup(text: Any, normalize: bool = True, collapse: bool = True) -> str:
    """
    Parses the given text and returns the text after stripping all MediaWiki
    markup, leaving only the plain text.

    :param normalize: passed to :py:func:`mwparserfromhell.wikicode.Wikicode.strip_code`
    :param collapse: passed to :py:func:`mwparserfromhell.wikicode.Wikicode.strip_code`
    :returns: :py:obj:`str`
    """
    wikicode = mwparserfromhell.parse(text)
    result = wikicode.strip_code(normalize, collapse)
    # wikicode.strip_code is untyped
    return cast(str, result)


def get_adjacent_node(
    wikicode: Wikicode, node: Node, ignore_whitespace: bool = False
) -> Node | None:
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
        n = cast(Node, wikicode.get(i))
        while ignore_whitespace and n.isspace():
            i += 1
            n = cast(Node, wikicode.get(i))
        return n
    except IndexError:
        return None


def get_parent_wikicode(wikicode: Wikicode, node: str | Node | Wikicode) -> Wikicode:
    """
    Returns the parent of `node` as a `wikicode` object.
    Raises :exc:`ValueError` if `node` is not a descendant of `wikicode`.
    """
    context, index = wikicode._do_strong_search(node, True)
    return cast(Wikicode, context)


def remove_and_squash(wikicode: Wikicode, obj: str | Node | Wikicode) -> None:
    """
    Remove `obj` from `wikicode` and fix whitespace in the place it was removed from.
    """
    parent = get_parent_wikicode(wikicode, obj)
    index = parent.index(obj)
    parent.remove(obj)

    def _get_text(index: int) -> tuple[None | mwparserfromhell.nodes.Text, None | type]:
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
        elif next_.startswith("\n"):  # pragma: no branch
            prev.value = prev.rstrip()
        # merge successive Text nodes
        prev.value += next_.value
        parent.remove(next_)


def get_section_headings(text: str) -> list[str]:
    """
    Extracts section headings from given text. Custom regular expression is used
    instead of :py:mod:`mwparserfromhell` for performance reasons.

    .. note::
        Known issues:

        - templates are not handled (use
          :py:func:`ws.parser_helpers.template_expansion.expand_templates`
          prior to calling this function)

    :param str text: content of the wiki page
    :returns: list of section headings (without the ``=`` marks)
    """
    # re.findall returns a list of tuples of the matched groups
    # gotcha: the line must start with '=', but does not have to end with '=' (trailing whitespace is ignored)
    matches = re.findall(
        r"^((\={1,6})[^\S\n]*)([^\n]+?)([^\S\n]*(\2))[^\S\n]*$",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    return [match[2] for match in matches]


def get_anchors(
    headings: list[str], pretty: bool = False, suffix_sep: str = "_"
) -> list[str]:
    """
    Converts section headings to anchors.

    .. note::
        Known issues:

        - templates are not handled (call
          :py:func:`ws.parser_helpers.template_expansion.expand_templates`
          on the wikitext before extracting section headings)
        - all tags are always stripped, even invalid tags
          (:py:mod:`mwparserfromhell` is not that configurable)
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
        anchors = [
            a.replace("[", "%5B").replace("|", "%7C").replace("]", "%5D")
            for a in anchors
        ]

    # handle equivalent headings duplicated on the page
    for i, anchor in enumerate(anchors):
        j = 2
        # this check should be case-insensitive, see https://wiki.archlinux.org/index.php/User:Lahwaacz/Notes#Section_anchors
        while anchor.lower() in [a.lower() for a in anchors[:i]]:
            anchor = anchors[i] + suffix_sep + "{}".format(j)
            j += 1
        # update the main array
        anchors[i] = anchor
    return anchors


def ensure_flagged_by_template(
    wikicode: Wikicode,
    node: Node,
    template_name: str,
    *template_parameters: str,
    overwrite_parameters: bool = True,
) -> mwparserfromhell.nodes.Template:
    """
    Makes sure that ``node`` in ``wikicode`` is immediately (except for
    whitespace) followed by a template with ``template_name`` and optional
    ``template_parameters``.

    :param wikicode: a :py:class:`mwparserfromhell.wikicode.Wikicode` object
    :param node: a :py:class:`mwparserfromhell.nodes.Node` object
    :param str template_name: the name of the template flag
    :param template_parameters: optional template parameters
    :returns: the template flag, as a
        :py:class:`mwparserfromhell.nodes.template.Template` object
    """
    parent = get_parent_wikicode(wikicode, node)
    adjacent = get_adjacent_node(parent, node, ignore_whitespace=True)

    if template_parameters:
        flag_str = "{{%s}}" % "|".join([template_name, *template_parameters])
    else:
        flag_str = "{{%s}}" % template_name
    flag = mwparserfromhell.parse(flag_str).nodes[0]
    assert isinstance(flag, mwparserfromhell.nodes.Template)

    if isinstance(adjacent, mwparserfromhell.nodes.Template) and adjacent.name.matches(
        template_name
    ):
        # in case of {{Dead link}} we want to preserve the original parameters
        if overwrite_parameters is True:
            wikicode.replace(adjacent, flag)
        else:
            flag = adjacent
    else:
        wikicode.insert_after(node, flag)

    assert get_parent_wikicode(wikicode, flag) is parent
    return flag


def ensure_unflagged_by_template(
    wikicode: Wikicode,
    node: Node,
    template_name: str,
    *,
    match_only_prefix: bool = False,
) -> None:
    """
    Makes sure that ``node`` in ``wikicode`` is not immediately (except for
    whitespace) followed by a template with ``template_name``.

    :param wikicode: a :py:class:`mwparserfromhell.wikicode.Wikicode` object
    :param node: a :py:class:`mwparserfromhell.nodes.Node` object
    :param str template_name: the name of the template flag
    :param bool match_only_prefix: if ``True``, only the prefix of the adjacent
                                   template must match ``template_name``
    """
    parent = get_parent_wikicode(wikicode, node)
    adjacent = get_adjacent_node(parent, node, ignore_whitespace=True)

    if isinstance(adjacent, mwparserfromhell.nodes.Template):
        if match_only_prefix is True:
            if canonicalize(adjacent.name).startswith(canonicalize(template_name)):
                remove_and_squash(wikicode, adjacent)
        else:
            if adjacent.name.matches(template_name):
                remove_and_squash(wikicode, adjacent)


def is_flagged_by_template(
    wikicode: Wikicode,
    node: Node,
    template_name: str,
    *,
    match_only_prefix: bool = False,
) -> bool:
    """
    Checks if ``node`` in ``wikicode`` is immediately (except for whitespace)
    followed by a template with ``template_name``.

    :param wikicode: a :py:class:`mwparserfromhell.wikicode.Wikicode` object
    :param node: a :py:class:`mwparserfromhell.nodes.Node` object
    :param str template_name: the name of the template flag
    :param bool match_only_prefix: if ``True``, only the prefix of the adjacent
                                   template must match ``template_name``
    """
    parent = get_parent_wikicode(wikicode, node)
    adjacent = get_adjacent_node(parent, node, ignore_whitespace=True)

    if isinstance(adjacent, mwparserfromhell.nodes.Template):
        if match_only_prefix is True:
            if canonicalize(adjacent.name).startswith(canonicalize(template_name)):
                return True
        else:
            if adjacent.name.matches(template_name):
                return True
    return False


def is_redirect(text: str, *, full_match: bool = False) -> bool:
    """
    Checks if the text represents a MediaWiki `redirect page`_.

    :param bool full_match:
        Restricts the behaviour to return ``True`` only for pages which do not
        contain anything else but the redirect line.

    .. _`redirect page`: https://www.mediawiki.org/wiki/Help:Redirects
    """
    if full_match is True:
        f = re.fullmatch
    else:
        f = re.match
    match = f(
        r"#redirect\s*:?\s*\[\[[^[\]{}]+\]\]",
        text.strip(),
        flags=re.MULTILINE | re.IGNORECASE,
    )
    return bool(match)


# default flags copied from mwparserfromhell
FLAGS = re.IGNORECASE | re.DOTALL | re.UNICODE


def parented_ifilter(
    wikicode: Wikicode,
    recursive: bool = True,
    matches: Callable | re.Pattern | None = None,
    flags: re.RegexFlag = FLAGS,
    forcetype: type | None = None,
) -> Generator[tuple[Wikicode, Node]]:
    """Iterate over nodes and their corresponding parents.

    The arguments are interpreted as for :meth:`ifilter`. For each tuple
    ``(parent, node)`` yielded by this method, ``parent`` is the direct
    parent wikicode of ``node``.

    The method is intended for performance optimization by avoiding expensive
    search e.g. in the ``replace`` method. See the :py:mod:`mwparserfromhell`
    issue for details: https://github.com/earwig/mwparserfromhell/issues/195
    """
    match = wikicode._build_matcher(matches, flags)
    inodes: Iterable[tuple[Wikicode, Node]]
    if recursive:
        restrict = forcetype if recursive == wikicode.RECURSE_OTHERS else None

        def getter(node: Node) -> Generator[tuple[Wikicode, Node]]:
            for parent, ch in wikicode._get_children(
                node, restrict=restrict, contexts=True, parent=wikicode
            ):
                yield (parent, cast(Node, ch))

        inodes = chain(*(getter(n) for n in wikicode.nodes))
    else:
        inodes = ((wikicode, cast(Node, node)) for node in wikicode.nodes)
    for parent, node in inodes:
        if (not forcetype or isinstance(node, forcetype)) and match(node):
            yield (parent, cast(Node, node))
