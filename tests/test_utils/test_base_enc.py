#! /usr/bin/env python3

import pytest

from ws.utils.base_enc import base_enc, base_dec


@pytest.mark.parametrize("encoded, base, decoded",
        [
            (b"1234567890", 10, 1234567890),
            (b"-1234567890", 10, -1234567890),
            (b"abcdef", 16, 0xabcdef),
            (b"abcdefghijklmnopqrstuvwxyz0123456789", 36,
             30483235087530204251026473460499750369628008625670311705),
        ])
def test_encdec(encoded, base, decoded):
    assert base_dec(encoded, base) == decoded
    assert base_enc(decoded, base) == encoded
