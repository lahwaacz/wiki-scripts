#! /usr/bin/env python3

import re
import string
import unicodedata

__all__ = ["encode", "decode", "dotencode", "anchorencode", "urlencode", "urldecode", "queryencode", "querydecode"]

def encode(str_, escape_char="%", encode_chars="", skip_chars="", special_map=None, charset="utf-8", errors="strict"):
    """
    Generalized implementation of a `percent encoding`_ algorithm.

    .. _`percent encoding`: https://en.wikipedia.org/wiki/Percent-encoding

    :param str_: the string to be encoded
    :param escape_char: character to be used as escape (by default '%')
    :param encode_chars: the characters to be encoded; empty string means that
        all characters will be encoded unless explicitly skipped
    :param skip_chars: characters to be skipped (applied after ``encode_chars``)
    :param special_map: a mapping overriding default encoding (applied after
        both ``encode_chars`` and ``skip_chars``)
    :param charset: character set used to encode non-ASCII characters to byte
        sequence with :py:meth:`str.encode()`
    :param errors: defines behaviour when encoding non-ASCII characters to bytes
        fails (passed to :py:meth:`str.encode()`)
    """
    output = ""
    for char in str_:
        if encode_chars == "" or char in encode_chars:
            if char not in skip_chars:
                if special_map is not None and char in special_map:
                    output += special_map[char]
                else:
                    for byte in bytes(char, charset, errors):
                        output += "{}{:02X}".format(escape_char, byte)
            else:
                output += char
        else:
            output += char
    return output

def decode(str_, escape_char="%", special_map=None, charset="utf-8", errors="strict"):
    """
    An inverse function to :py:func:`encode`.

    .. note::
        The reversibility of the encoding depends on the parameters passed to
        :py:func:`encode`. Specifically, if the `escape_char` is not encoded,
        the operation is irreversible. Unfortunately MediaWiki does this with
        dot-encoding, so don't even try to decode dot-encoded strings!

    :param str_: the string to be decoded
    :param escape_char: character to be used as escape (by default '%')
    :param special_map: an analogue to the same parameter in :py:func:`encode`
        (the caller is responsible for inverting the mapping they passed to
        :py:func:`encode`)
    :param charset:
        character set used to decode byte sequence with :py:meth:`bytes.decode()`
    :param errors:
        defines behaviour when byte-decoding with :py:meth:`bytes.decode()` fails
    """
    tok = re.compile(escape_char + "([0-9A-Fa-f]{2})|(.)", re.DOTALL)
    output = ""
    barr = bytearray()
    for match in tok.finditer(str_):
        enc_couple, char = match.groups()
        if enc_couple:
            barr.append(int(enc_couple, 16))
        else:
            if len(barr) > 0:
                output += barr.decode(charset, errors)
                barr = bytearray()
            if special_map is not None and char in special_map:
                output += special_map[char]
            else:
                output += char
    if len(barr) > 0:
        output += barr.decode(charset, errors)
    return output

def _anchor_preprocess(str_):
    """
    Context-sensitive pre-processing for anchor-encoding. See `MediaWiki`_ for
    details.

    .. _`MediaWiki`: https://www.mediawiki.org/wiki/Manual:PAGENAMEE_encoding
    """
    # underscores are treated as spaces during this pre-processing, so they are
    # converted to spaces first (the encoding later converts them back)
    str_ = str_.replace("_", " ")
    # strip leading + trailing whitespace
    str_ = str_.strip()
    # squash *spaces* in the middle (other whitespace is preserved)
    str_ = re.sub("[ ]+", " ", str_)
    # leading colons are stripped, others preserved (colons in the middle preceded by
    # newline are supposed to be fucked up in MediaWiki, but this is pretty safe to ignore)
    str_ = str_.lstrip(":")
    return str_

def dotencode(str_):
    """
    Return an anchor-encoded string as shown in this `encoding table`_. It uses
    the ``legacy`` format for `$wgFragmentMode`_.

    .. note::
        The rules for handling special characters in section anchors are not
        well defined even upstream, see `T20431`_. This function produces the
        actual anchor for the section, i.e. the ID of the heading's span element
        (e.g. ``<span id="anchor" ...>``).

    .. _`encoding table`: https://www.mediawiki.org/wiki/Manual:PAGENAMEE_encoding#Encodings_compared
    .. _`T20431`: https://phabricator.wikimedia.org/T20431
    .. _`$wgFragmentMode`: https://www.mediawiki.org/wiki/Manual:$wgFragmentMode
    """
    skipped = string.ascii_letters + string.digits + "-_.:"
    special = {" ": "_"}
    return encode(_anchor_preprocess(str_), escape_char=".", skip_chars=skipped, special_map=special)

def anchorencode(str_, format="html5"):
    """
    Function corresponding to the ``{{anchorencode:}}`` `magic word`_.

    .. note::
        The rules for handling special characters in section anchors are not
        well defined even upstream, see `T20431`_ and `T30212`_.

    :param str_: the string to be encoded
    :param format: either ``"html5"`` or ``"legacy"`` (see `$wgFragmentMode`_)

    .. _`magic word`: https://www.mediawiki.org/wiki/Help:Magic_words
    .. _`T20431`: https://phabricator.wikimedia.org/T20431
    .. _`T30212`: https://phabricator.wikimedia.org/T30212
    .. _`$wgFragmentMode`: https://www.mediawiki.org/wiki/Manual:$wgFragmentMode
    """
    if format not in {"html5", "legacy"}:
        raise ValueError(format)
    if format == "legacy":
        return dotencode(str_)
    str_ = _anchor_preprocess(str_)
    # encode "%" from percent-encoded octets
    str_ = re.sub(r"%([a-fA-F0-9]{2})", r"%25\g<1>", str_)
    # html5 spec says ids must not contain spaces (although only
    # some of them are possible in wikitext using either Lua or
    # HTML entities)
    special_map = dict((c, "_") for c in string.whitespace)
    escape_char = "%"
    charset = "utf-8"
    errors = "strict"
    # encode sensitive characters - the output of this function should be usable
    # in MediaWiki links
    # MW incompatibility: MediaWiki's safeEncodeAttribute sanitizer function
    # replaces even more tokens with HTML entities, but they do not appear in
    # the output of the {{anchorencode:}} magic word (substituted back into the
    # original characters in a next parse stage?)
    encode_chars = "[]|"
    # below is the code from the encode function, but without the skip_chars
    # parameter and adjusted for unicode categories
    output = ""
    for char in str_:
        # encode only characters from the Separator and Other categories
        # https://en.wikipedia.org/wiki/Unicode#General_Category_property
        if char in encode_chars or unicodedata.category(char)[0] in {"Z", "C"}:
            if special_map is not None and char in special_map:
                output += special_map[char]
            else:
                for byte in bytes(char, charset, errors):
                    output += "{}{:02X}".format(escape_char, byte)
        else:
            output += char
    return output

def urlencode(str_):
    """
    Standard URL encoding as described on `Wikipedia`_, which should correspond
    to the ``PATH`` style in the MediaWiki's `comparison table`_.

    .. _`Wikipedia`: https://en.wikipedia.org/wiki/Percent-encoding
    .. _`comparison table`: https://www.mediawiki.org/wiki/Manual:PAGENAMEE_encoding#Encodings_compared
    """
    skipped = string.ascii_letters + string.digits + "-_.~"
    return encode(str_, skip_chars=skipped)

def urldecode(str_):
    """
    An inverse function to :py:func:`urlencode`.
    """
    return decode(str_)

def queryencode(str_):
    """
    The ``QUERY`` style encoding as described on `MediaWiki`_. This is the
    default URL encoding in MediaWiki since 1.17.

    .. _`MediaWiki`: https://www.mediawiki.org/wiki/Manual:PAGENAMEE_encoding#Encodings_compared
    """
    skipped = string.ascii_letters + string.digits + "-_."
    special = {" ": "+"}
    return encode(str_, skip_chars=skipped, special_map=special)

def querydecode(str_):
    """
    An inverse function to :py:func:`queryencode`.
    """
    special = {"+": " "}
    return decode(str_, special_map=special)
