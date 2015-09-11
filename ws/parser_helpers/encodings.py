#! /usr/bin/env python3

import string
import re

__all__ = ["encode", "dotencode", "urlencode", "queryencode"]

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

def _anchor_preprocess(str_):
    """
    Context-sensitive pre-processing for anchor-encoding. See `MediaWiki`_ for
    details.

    .. _`MediaWiki`: https://www.mediawiki.org/wiki/Manual:PAGENAMEE_encoding
    """
    # underscores are treated as spaces during this pre-processing, so they are
    # convert to spaces first (the encoding later converts them back)
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
    Return an anchor-encoded string as shown in this `encoding table`_.

    .. _`encoding table`: https://www.mediawiki.org/wiki/Manual:PAGENAMEE_encoding#Encodings_compared
    """
    skipped = string.ascii_letters + string.digits + "-_.:"
    special = {" ": "_"}
    return encode(_anchor_preprocess(str_), escape_char=".", skip_chars=skipped, special_map=special)

def urlencode(str_):
    """
    Standard URL encoding as described on `Wikipedia`_, which should correspond
    to the ``PATH`` style in the MediaWiki's `comparison table`_.

    .. _`Wikipedia`: https://en.wikipedia.org/wiki/Percent-encoding
    .. _`comparison table`: https://www.mediawiki.org/wiki/Manual:PAGENAMEE_encoding#Encodings_compared
    """
    skipped = string.ascii_letters + string.digits + "-_.~"
    return encode(str_, skip_chars=skipped)

def queryencode(str_):
    """
    The ``QUERY`` style encoding as described on `MediaWiki`_. This is the
    default URL encoding in MediaWiki since 1.17.

    .. _`MediaWiki`: https://www.mediawiki.org/wiki/Manual:PAGENAMEE_encoding#Encodings_compared
    """
    skipped = string.ascii_letters + string.digits + "-_."
    special = {" ": "+"}
    return encode(str_, skip_chars=skipped, special_map=special)
