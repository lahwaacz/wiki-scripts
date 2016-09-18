#! /usr/bin/env python3

"""
Custom types with automatic convertors.

Note that we can't use *TEXT instead of *BLOB types, nor *CHAR instead of
*BINARY, because although they have the same size and hold an encoding for
automatic conversion, all server-side operations are case-insensitive.

For compatibility with MediaWiki schema we keep custom timestamp converters
instead of using the TIMESTAMP SQL type.

References:
 - http://dev.mysql.com/doc/refman/5.7/en/blob.html
 - http://docs.sqlalchemy.org/en/latest/core/custom_types.html
"""

import sqlalchemy.types as types
from sqlalchemy.dialects.mysql import TINYBLOB, BLOB, MEDIUMBLOB, LONGBLOB

from ws.utils import base_enc, base_dec


class _UnicodeConverter(types.TypeDecorator):
    def __init__(self, *args, charset="utf8", **kwargs):
        super().__init__(*args, **kwargs)
        self.charset = charset

    def process_bind_param(self, value, dialect):
        if isinstance(value, str):
            return bytes(value, self.charset)
        return value

    def process_result_value(self, value, dialect):
        return str(value, self.charset)


class TinyBlob(_UnicodeConverter):
    """
    TINYBLOB with automatic conversion to Python str.
    """
    impl = TINYBLOB


class Blob(_UnicodeConverter):
    """
    BLOB with automatic conversion to Python str.
    """
    impl = BLOB


class MediumBlob(_UnicodeConverter):
    """
    MEDIUMBLOB with automatic conversion to Python str.
    """
    impl = MEDIUMBLOB


class LongBlob(_UnicodeConverter):
    """
    LONGBLOB with automatic conversion to Python str.
    """
    impl = LONGBLOB


class UnicodeBinary(_UnicodeConverter):
    """
    VARBINARY with automatic conversion to Python str.
    """
    impl = types.VARBINARY


class MWTimestamp(types.TypeDecorator):
    """
    Custom type for representing MediaWiki timestamps.
    """

    impl = types.BINARY(14)

    def __init__(self, charset="utf8"):
        self.charset = charset

    def process_bind_param(self, value, dialect):
        """
        Convert timestamp from MediaWiki to database format, i.e.
        2013-01-05T01:16:52Z --> 20130105011652
        """
        if value is None:
            return value
        # TODO: there should be some validation (which would probably make this very slow)
        # special values like "infinity" are handled implicitly
        value = value.replace('-', '').replace('T', '').replace(':', '').replace('Z', '')
        return bytes(value, self.charset)

    def process_result_value(self, value, dialect):
        """
        Convert timestamp from database to MediaWiki format, i.e.
        20130105011652 --> 2013-01-05T01:16:52Z
        """
        ts = str(value.rstrip(b"\0"), self.charset)
        if ts == "infinity":
            return ts
        r = ts[:4] + "-" + ts[4:6] + "-" + ts[6:8] + "T" + \
            ts[8:10] + ":" + ts[10:12] + ":" + ts[12:14] + "Z"
        return r


class Base36(types.TypeDecorator):
    """
    Convertor between base36 number and Python str.

    For example MediaWiki stores SHA1 sums this way.
    """

    impl = types.BINARY

    def process_bind_param(self, value, dialect):
        """
        python -> db
        """
        n = base_dec(bytes(value, "ascii"), 16)
        return base_enc(n, 36)

    def process_result_value(self, value, dialect):
        """
        db -> python
        """
        n = base_dec(value, 36)
        return str(base_enc(n, 16), "ascii")
