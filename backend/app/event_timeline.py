"""Bounded keyset timeline queries; every caller must apply current camera ACLs."""
import base64
from collections import Counter
from datetime import datetime, timezone
import json
import re
from uuid import UUID

from fastapi import HTTPException


def utc(value):
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('timezone required')
    return value.astimezone(timezone.utc)


def encode_cursor(record):
    payload = {'time': utc(datetime.fromisoformat(record['detected_at'].replace('Z', '+00:00'))).isoformat(),
               'id': str(UUID(record['id']))}
    return base64.urlsafe_b64encode(json.dumps(payload, separators=(',', ':')).encode()).decode()


def decode_cursor(value):
    try:
        if not isinstance(value,str) or not 0<len(value)<=512 or not re.fullmatch(r'[A-Za-z0-9_-]+={0,2}',value):
            raise ValueError('cursor size')
        decoded=base64.b64decode(value, altchars=b'-_', validate=True)
        if base64.urlsafe_b64encode(decoded).decode('ascii')!=value:
            raise ValueError('noncanonical cursor')
        payload = json.loads(decoded)
        if set(payload) != {'time', 'id'} or not isinstance(payload['time'], str):
            raise ValueError('cursor fields')
        return utc(datetime.fromisoformat(payload['time'].replace('Z', '+00:00'))).isoformat(), str(UUID(payload['id']))
    except (ValueError, TypeError, KeyError, AttributeError):
        raise HTTPException(422, 'Cursor de eventos inválido') from None


def configure_timeline(query, camera_ids, *, event_type=None, review_status=None,
                       since=None, until=None, cursor=None, limit=100):
    try:
        since = utc(since) if since else None
        until = utc(until) if until else None
        if since and until and since > until:
            raise ValueError('range')
    except ValueError:
        raise HTTPException(422, 'El periodo requiere fechas con zona horaria y orden válido') from None
    position = decode_cursor(cursor) if cursor else None
    query = query.in_('camera_id', camera_ids)
    if event_type:
        query = query.eq('event_type', event_type)
    if review_status:
        query = query.eq('review_status', review_status)
    if since:
        query = query.gte('detected_at', since.isoformat())
    if until:
        query = query.lte('detected_at', until.isoformat())
    if position:
        stamp, identifier = position
        # Values are canonical UTC/UUID, never raw PostgREST filter expressions.
        query = query.or_(f'detected_at.lt.{stamp},and(detected_at.eq.{stamp},id.lt.{identifier})')
    return query.order('detected_at', desc=True).order('id', desc=True).limit(limit + 1)


def page_metadata(records, limit):
    has_more = len(records) > limit
    page = records[:limit]
    return page, {
        'has_more': has_more,
        'next_cursor': encode_cursor(page[-1]) if has_more else None,
        'summary': {
            'scope': 'page',
            'by_type': dict(Counter(r.get('event_type', 'motion_detected') for r in page)),
            'by_review_status': dict(Counter(r.get('review_status') or 'pending' for r in page)),
        },
    }
