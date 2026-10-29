"""Application mitigations for ambiguous Base64 and bounded JWT parser input."""
import base64
from uuid import UUID

import jwt
import pytest
from fastapi import HTTPException

from app.event_timeline import decode_cursor,encode_cursor
from app import streaming

ALPHABET='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'


def test_cursor_rejects_equivalent_noncanonical_padding_bits():
    cursor=encode_cursor({'id':str(UUID(int=1)),'detected_at':'2026-10-28T12:00:00+00:00'})
    bare=cursor.rstrip('=')
    assert cursor.endswith('=')
    variant=bare[:-1]+ALPHABET[ALPHABET.index(bare[-1])+1]+cursor[len(bare):]
    assert base64.b64decode(cursor,altchars=b'-_',validate=True)==base64.b64decode(variant,altchars=b'-_',validate=True)
    assert decode_cursor(cursor)==('2026-10-28T12:00:00+00:00',str(UUID(int=1)))
    with pytest.raises(HTTPException) as error:decode_cursor(variant)
    assert error.value.status_code==422


@pytest.mark.parametrize('value',['','a'*513,'a+b/','====','YWJj====','YWJj\n',b'YWJj',None])
def test_cursor_rejects_non_url_alphabet_and_malformed_input(value):
    with pytest.raises(HTTPException) as error:decode_cursor(value)
    assert error.value.status_code==422


@pytest.mark.parametrize('token',['x'*8193,b'x'*8193,'',None])
def test_large_or_empty_stream_token_never_reaches_jwt_parser(monkeypatch,token):
    def forbidden(*args,**kwargs):raise AssertionError('unbounded parser input')
    monkeypatch.setattr(streaming.jwt,'decode',forbidden)
    with pytest.raises(ValueError):streaming.verify_stream(token,'cam_fixture')


def test_upstream_jwt_canonicalization_is_preserved(monkeypatch):
    monkeypatch.setenv('STREAM_TOKEN_SECRET','isolated-phase7-fixture-signing-key-only')
    camera={'id':'fixture','user_id':'owner','organization_id':None}
    token=streaming.issue_stream('fixture',camera)['stream_token']
    assert streaming.verify_stream(token,'cam_fixture')['sub']=='fixture'
    header,payload,signature=token.split('.')
    variant=signature[:-1]+ALPHABET[ALPHABET.index(signature[-1])+1]
    with pytest.raises(jwt.DecodeError):streaming.verify_stream('.'.join((header,payload,variant)),'cam_fixture')
