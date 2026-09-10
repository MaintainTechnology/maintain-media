"""Read-only HTTPS smoke check using the newly escrowed server assertion key.

This verifies the server transport, not a browser Clerk login. Never prints keys,
tokens, provider bodies or business values. It reads no existing env files.
"""
import hashlib
import json
import time
from pathlib import Path
from uuid import uuid4

import httpx
import jwt
from provision_runtime_client import Escrow


def check():
    escrow = Escrow(Path('C:/Users/dalig/AppData/Local/MaintainMedia/aws/runtime-key-escrow/abn-leadgen-sydney-20260910.dpapi'))
    state = escrow.load()
    if state['stage'] != 'complete':
        raise ValueError('Installation incomplete')
    request_id, now = str(uuid4()), int(time.time())
    claims = {'iss': 'maintain-media-website', 'aud': 'abr-engine-live',
              'sub': 'user_3J8dBsvcl9AGXTGOCbAzjYIH9sU', 'iat': now, 'exp': now + 60,
              'jti': str(uuid4()), 'scopes': ['admin', 'operator', 'reviewer'],
              'method': 'GET', 'path': '/api/dashboard',
              'body_sha256': hashlib.sha256(b'').hexdigest(),
              'request_id': request_id, 'idempotency_key': ''}
    token = jwt.encode(claims, state['material']['website_assertion_key'], algorithm='HS256')
    with httpx.Client(trust_env=False, follow_redirects=False, timeout=20) as client:
        response = client.get('https://abn-engine.maintainmedia.com.au/api/dashboard',
                              headers={'Authorization': 'Bearer ' + token, 'X-Request-ID': request_id})
    if response.status_code != 200:
        return {'status': 'failed', 'http_status': response.status_code, 'browser_login_verified': False}
    data = response.json()
    if data.get('mode') != 'pilot' or data.get('outreach') != 'disabled':
        raise ValueError('Unexpected runtime mode')
    website_rows = [row for row in data.get('setup', []) if row.get('id') == 'website_collection']
    return {'status': 'authenticated_runtime_verified', 'http_status': 200,
            'mode': data['mode'], 'outreach': data['outreach'],
            'lead_count': data['summary']['total_leads'], 'selected_count': data['summary']['selected'],
            'worker_connected': data['run_enabled'], 'browser_login_verified': False,
            'website_collection_separately_blocked': len(website_rows) == 1
            and website_rows[0].get('status') == 'blocked'
            and website_rows[0].get('detail') == 'Required evidence: CAPABILITY_DISABLED',
            'cache_control': response.headers.get('cache-control')}


if __name__ == '__main__':
    try:
        result = check()
    except Exception:  # noqa: BLE001 -- never reflect secret-bearing provider or escrow errors
        result = {'status': 'failed', 'code': 'RUNTIME_PROBE_UNCONFIRMED', 'browser_login_verified': False}
    print(json.dumps(result))
    raise SystemExit(0 if result['status'] == 'authenticated_runtime_verified' else 2)
