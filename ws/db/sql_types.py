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
"""

import json
import datetime

import sqlalchemy.types as types

from ws.utils import base_enc, base_dec, DatetimeEncoder, datetime_parser


# TODO: drop the MySQL-like aliases and use the underlying type directly in the schema
TinyBlob = types.UnicodeText
Blob = types.UnicodeText
MediumBlob = types.UnicodeText
LongBlob = types.UnicodeText

# MediaWiki's PostgreSQL schema uses TEXT for just about everyting, i.e. no
# VARCHAR. PostreSQL's manual says that there is no performance difference
# between char(n), varchar(n) and text:
#     https://www.postgresql.org/docs/current/static/datatype-character.html
# We should probably drop the length limits as well to make migrations easy.
# Plus, the MySQL limits are in *bytes*, whereas textual types are measured in
# characters. Therefore we follow the PostgreSQL schema and use TEXT instead of
# VARCHAR.
class UnicodeBinary(types.TypeDecorator):
    impl = types.UnicodeText
    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)


# TODO: switch to types.DateTime (without timezone) and do the serialization to string on the API side
# TODO: find out how to use the infinity constant: https://www.postgresql.org/docs/9.6/static/datatype-datetime.html#DATATYPE-DATETIME-SPECIAL-TABLE
class MWTimestamp(types.TypeDecorator):
    """
    Convertor for TIMESTAMP handling infinite values.
    """

    # MW incompatibility: MediaWiki's PostgreSQL schema uses TIMESTAMPTZ instead
    # of TIMESTAMP.
    impl = types.DateTime(timezone=False)

    def process_bind_param(self, value, dialect):
        """
        Python -> database
        """
        assert dialect.name == "postgresql"
        if value is None:
            return value
        assert isinstance(value, datetime.datetime)
        if value == datetime.datetime.max:
            return b"'infinity'::date"
        elif value == datetime.datetime.min:
            return b"'-infinity'::date"
        else:
            return value

    def process_result_value(self, value, dialect):
        """
        database -> python
        """
        assert dialect.name == "postgresql"
        if value is None:
            return value
        if value == b"'infinity'::date":
            return datetime.datetime.max
        elif value == b"'-infinity'::date":
            return datetime.datetime.min
        else:
            return value


class SHA1(types.TypeDecorator):
    """
    Convertor for the SHA1 hashes.

    In MediaWiki they are represented as a base36-encoded number in the database
    and as a hexadecimal string in the API.

    In both forms the encoded string has to be padded with zeros to fixed
    length - 31 digits in base36, 40 digits in hex.
    """

#    impl = types.BINARY(length=31)
    impl = types.LargeBinary(length=31)

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
            value = json.dumps(value, cls=DatetimeEncoder)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value, object_hook=datetime_parser)
        return value
