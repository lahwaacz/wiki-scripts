#! /usr/bin/env python3

"""
Custom types with automatic convertors.

Advantages of textual types:
    - natural for the representation of textual (Unicode) data

Disadvantages of textual types:
    - subject to encoding and collation

Advantages of binary types:
    - complete control over the data representation and conversion to Python
      objects
    - length is in bytes, so there is no storage overhead for ASCII-only data

In MySQL, textual types (*TEXT, *CHAR) represent Unicode strings, but all utf8
collations are case-insensitive: http://stackoverflow.com/a/4558736/4180822
On the other hand, binary types (*BLOB, *BINARY) are treated as "byte strings",
i.e. ASCII text with binary collation.

In PostgreSQL, the binary type (bytea) does not represent "strings", i.e. there
are much less operations and functions defined on bytea then in MySQL for
binary strings. By using the textual types, we also benefit from native
conversion functions in the sqlalchemy driver (e.g. psycopg2).

TODO: MediaWiki's PostgreSQL schema uses TEXT for just about everyting, i.e. no
      VARCHAR. PostreSQL's manual says that there is no performance difference
      between char(n), varchar(n) and text:
          https://www.postgresql.org/docs/current/static/datatype-character.html
      We should probably drop the length limits as well to make migrations easy.
      Plus, the MySQL limits are in *bytes*, whereas textual types are measured
      in characters.
"""

import json

import sqlalchemy.types as types
from sqlalchemy.dialects.mysql import TINYBLOB, BLOB, MEDIUMBLOB, LONGBLOB

from ws.utils import base_enc, base_dec


# TODO: drop along with MySQL support
class _UnicodeConverter(types.TypeDecorator):
    def __init__(self, *args, **kwargs):
        # we need to pass the parameters to the underlying type in load_dialect_impl ourselves
        super().__init__()
        self._args = args
        self._kwargs = kwargs
        self.charset = "utf8"

    def process_bind_param(self, value, dialect):
        # use native unicode conversion for dialects where we use textual types
        if dialect.name == "postgresql":
            return value
        else:
            if isinstance(value, str):
                return bytes(value, self.charset)
            return value

    def process_result_value(self, value, dialect):
        # use native unicode conversion for dialects where we use textual types
        if dialect.name == "postgresql":
            return value
        else:
            if value is None:
                return value
            return str(value, self.charset)

    def load_dialect_impl(self, dialect):
        if dialect.name == "mysql":
            return dialect.type_descriptor(self.impl)
        elif dialect.name == "postgresql":
            return dialect.type_descriptor(types.UnicodeText(*self._args, **self._kwargs))
        else:
            # generic variable-length binary
            return dialect.type_descriptor(types.LargeBinary(*self._args, **self._kwargs))


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
    impl = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def load_dialect_impl(self, dialect):
        if dialect.name == "mysql":
            return dialect.type_descriptor(types.VARBINARY(*self._args, **self._kwargs))
        else:
            # otherwise use VARCHAR with driver's native unicode encoding
            return dialect.type_descriptor(types.VARCHAR(*self._args, **self._kwargs))


# TODO: switch to types.DateTime (without timezone) and do the serialization to string on the API side
# TODO: find out how to use the infinity constant: https://www.postgresql.org/docs/9.6/static/datatype-datetime.html#DATATYPE-DATETIME-SPECIAL-TABLE
class MWTimestamp(types.TypeDecorator):
    """
    Custom type for representing MediaWiki timestamps.

    MediaWiki uses BINARY(14) on MySQL and TIMESTAMPTZ on PostgreSQL.
    """

    impl = types.String(14)

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
        return value

    def process_result_value(self, ts, dialect):
        """
        Convert timestamp from database to MediaWiki format, i.e.
        20130105011652 --> 2013-01-05T01:16:52Z
        """
        if ts is None:
            return ts
        if ts == "infinity":
            return ts
        r = ts[:4] + "-" + ts[4:6] + "-" + ts[6:8] + "T" + \
            ts[8:10] + ":" + ts[10:12] + ":" + ts[12:14] + "Z"
        return r


# TODO: drop along with MySQL support, SHA1 should use the underlying type directly
class Binary(types.TypeDecorator):
    """ "Small" binary for mysql dialect, LargeBinary for others. """

    impl = None

    def __init__(self, length=None):
        super().__init__()
        self.length = length

    def load_dialect_impl(self, dialect):
        if dialect.name == "mysql":
            return dialect.type_descriptor(types.BINARY(length=self.length))
        else:
            return dialect.type_descriptor(types.LargeBinary(length=self.length))


class SHA1(types.TypeDecorator):
    """
    Convertor for the SHA1 hashes.

    In MediaWiki they are represented as a base36-encoded number in the database
    and as a hexadecimal string in the API.

    In both forms the encoded string has to be padded with zeros to fixed
    length - 31 digits in base36, 40 digits in hex.
    """

    impl = Binary(31)

    def process_bind_param(self, value, dialect):
        """
        python -> db
        """
        if value is None:
            return value
        n = base_dec(bytes(value, "ascii"), 16)
        return base_enc(n, 36).zfill(31)

    def process_result_value(self, value, dialect):
        """
        db -> python
        """
        if value is None:
            return value
        n = base_dec(value, 36)
        return str(base_enc(n, 16), "ascii").zfill(40)


# TODO: PostgreSQL has a JSON type, psycopg2 might have native conversion. We could also use the HSTORE type.
class JSONEncodedDict(types.TypeDecorator):
    """
    Represents an immutable structure as a JSON-encoded string.
    """

    impl = types.UnicodeText

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        return value
