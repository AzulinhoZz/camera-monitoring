"""Small decoder regressions; no resource-exhaustion payload or wall-clock threshold."""
import pytest
from pyasn1.codec.ber.decoder import decode
from pyasn1.error import PyAsn1Error


@pytest.mark.parametrize('encoded', [
    b'\x24\x08\x24\x06\x04\x01A\x04\x01B',
    b'\x24\x80\x24\x06\x04\x01A\x04\x01B\x00\x00',
])
def test_nested_constructed_octets_return_logical_value(encoded):
    value, rest = decode(encoded)
    assert value.asOctets() == b'AB'
    assert rest == b''


def test_constructed_bits_preserve_non_octet_aligned_fragment():
    value, rest = decode(b'\x23\x08\x03\x02\x00\xa5\x03\x02\x04\xf0')
    assert value.asBinary() == '101001011111'
    assert rest == b''


def test_invalid_bit_padding_is_rejected():
    with pytest.raises(PyAsn1Error):
        decode(b'\x23\x04\x03\x02\x08\xff')
