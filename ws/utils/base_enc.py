#! /usr/bin/env python3

def base_dec(string, base):
    """
    Return a decimal form of a number in given base.
    """
    return int(string, base)

def base_enc(number, base):
    """
    Encode a number in given base.
    """
    if base > 36:  # pragma: no cover
        raise NotImplementedError

    alphabet = b"0123456789abcdefghijklmnopqrstuvwxyz"
    encoded = bytearray()
    sign = b""

    if number < 0:
        sign = b"-"
        number = -number

    while number != 0:
        number, i = divmod(number, base)
        encoded.insert(0, alphabet[i])
    if sign:
        encoded.insert(0, sign[0])
    return encoded
