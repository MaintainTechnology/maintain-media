/* eslint-disable @typescript-eslint/no-require-imports -- Node CommonJS HTTP verification. */
/**
 * Clerk signed-out HTTP smoke. Never reads credentials, creates accounts, signs in,
 * or bypasses Clerk. The earlier local-password browser harness is retired.
 * Real signed-in/admin workflows require a user-completed Clerk session and are
 * verified separately; this receipt must never be presented as that evidence.
 */
const fs = require('node:fs/promises');
const path = require('node:path');

class SmokeError extends Error {}
const expect = (condition, message) => { if (!condition) throw new SmokeError(message); };

function localOrigin() {
  try {
    const url = new URL(process.env.ABN_DASHBOARD_TEST_URL || 'http://127.0.0.1:3001');
    if (!['http:', 'https:'].includes(url.protocol)
      || !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)
      || url.username || url.password || url.pathname !== '/' || url.search || url.hash || url.port === '0') {
      throw new Error();
    }
    return url.origin;
  } catch { throw new SmokeError('ABN_DASHBOARD_TEST_URL must be a plain loopback HTTP(S) origin.'); }
}

async function main() {
  const origin = localOrigin();
  const checks = [];
  const run = async (name, action) => {
    try {
      await action();
      checks.push({ name, status: 'passed' });
    } catch (error) {
      checks.push({ name, status: 'failed', error: error instanceof SmokeError ? error.message : 'Request or local source verification failed.' });
    }
  };
  const request = async (route, options = {}, inspect) => {
    const response = await fetch(origin + route, { ...options, redirect: 'manual', signal: AbortSignal.timeout(30000) });
    try { return await inspect(response); }
    finally { await response.body?.cancel().catch(() => {}); }
  };
  const privateResponse = (response, signedOutPage = false) => {
    const cache = response.headers.get('cache-control') || '';
    // Next dev overrides page headers with mandatory revalidation. Accept that
    // only for signed-out HTML/redirects; every data/action/report API stays strict.
    const privateNoStore = cache.includes('private') && cache.includes('no-store');
    const developmentPage = signedOutPage && cache.includes('no-cache') && cache.includes('must-revalidate');
    expect(privateNoStore || developmentPage, 'Private response must not be reused from cache.');
    expect((response.headers.get('x-robots-tag') || '').includes('noindex'), 'Private response must be excluded from indexing.');
    expect(response.headers.get('x-frame-options') === 'DENY', 'Private response must deny framing.');
  };
  const redirectTo = (response, route) => {
    expect([303, 307, 308].includes(response.status), `Expected a redirect; received HTTP ${response.status}.`);
    let destination;
    try { destination = new URL(response.headers.get('location') || '', origin); } catch { throw new SmokeError('Redirect destination is invalid.'); }
    expect(destination.origin === origin && destination.pathname === route, `Expected a local redirect to ${route}.`);
  };

  for (const route of ['/', '/services', '/about', '/contact']) {
    await run(`Public ${route} remains accessible`, () => request(route, {}, response => {
      expect(response.status === 200, `Expected HTTP 200; received HTTP ${response.status}.`);
    }));
  }
  for (const route of ['/sign-in', '/sign-up']) {
    await run(`Clerk ${route} page is available and private`, () => request(route, {}, response => {
      expect(response.status === 200, `Expected HTTP 200; received HTTP ${response.status}.`);
      expect(response.headers.get('x-maintain-workspace') === 'maintain-media-auth', 'Expected Maintain Media auth page.');
      privateResponse(response, true);
    }));
  }
  await run('Existing ABN sign-in redirects to Clerk sign-in', () => request('/abn-lead-gen/sign-in', {}, response => redirectTo(response, '/sign-in')));
  await run('Workspace index redirects to dashboard', () => request('/abn-lead-gen', {}, response => redirectTo(response, '/abn-lead-gen/dashboard')));
  for (const route of ['/abn-lead-gen/dashboard', '/abn-lead-gen/access']) {
    await run(`Signed-out ${route} requires Clerk sign-in`, () => request(route, {}, response => {
      redirectTo(response, '/sign-in');
      privateResponse(response, true);
    }));
  }

  const id = '00000000-0000-4000-8000-000000000001';
  const endpoints = [
    ['GET', '/dashboard'], ['HEAD', '/dashboard'], ['GET', `/jobs/${id}`],
    ['GET', `/reports/${id}/html`], ['GET', `/reports/${id}/csv`], ['GET', `/reports/${id}/markdown`],
    ['HEAD', `/reports/${id}/html`], ['PATCH', '/settings'], ['POST', '/runs'],
  ];
  for (const legacy of [false, true]) {
    for (const [method, route] of endpoints) {
      await run(`${legacy ? 'Forged legacy cookie' : 'Signed-out'} ${method} ${route} is denied before engine access`, () => {
        const mutation = ['POST', 'PATCH'].includes(method);
        return request('/api/abn-lead-gen' + route, {
          method,
          headers: {
            Accept: 'application/json',
            ...(legacy ? { Cookie: 'maintain_abn_admin=retired-invalid-cookie' } : {}),
            ...(mutation ? { Origin: origin, 'Content-Type': 'application/json', 'X-Admin-CSRF': 'invalid-test-token' } : {}),
          },
          ...(mutation ? { body: '{}' } : {}),
        }, async response => {
          expect(response.status === 401, `Expected HTTP 401; received HTTP ${response.status}.`);
          privateResponse(response);
          if (method !== 'HEAD') {
            const body = await response.json();
            expect(body?.code === 'ADMIN_SIGN_IN_REQUIRED', 'Expected the bounded Clerk sign-in error.');
          }
        });
      });
    }
  }
  for (const endpoint of ['login', 'logout']) {
    await run(`Retired local ${endpoint} endpoint returns 410 without a session cookie`, () => request(`/api/abn-lead-gen/auth/${endpoint}`, {
      method: 'POST', headers: { Origin: origin, 'Content-Type': 'application/json' }, body: '{}',
    }, async response => {
      expect(response.status === 410, `Expected HTTP 410; received HTTP ${response.status}.`);
      privateResponse(response);
      expect(!response.headers.has('set-cookie'), 'Retired endpoint must never issue a cookie.');
      const body = await response.json();
      expect(body?.code === 'CLERK_AUTH_REQUIRED' && body?.signInUrl === '/sign-in', 'Expected bounded Clerk migration guidance.');
    }));
  }
  await run('Next proxy declares one Clerk auto-proxy matcher after API/TRPC', async () => {
    const source = await fs.readFile(path.join(__dirname, '../src/proxy.ts'), 'utf8');
    const entries = [...source.matchAll(/["'](\/__clerk\/:path\*)["']/g)];
    expect(entries.length === 1, 'Expected exactly one Clerk auto-proxy matcher.');
    const api = source.search(/["']\/\(api\|trpc\)\(\.\*\)["']/);
    expect(api >= 0 && api < entries[0].index, 'Clerk auto-proxy matcher must follow API/TRPC.');
  });

  const failed = checks.filter(check => check.status === 'failed');
  const result = {
    status: failed.length ? 'failed' : 'passed', checked_at: new Date().toISOString(),
    scope: 'Signed-out HTTP access, retired-password denial, and local proxy source only. Real Clerk account creation, sign-in, admin access and sign-out are not covered.',
    cache_qualification: 'Signed-out HTML and redirects accept Next development no-cache, must-revalidate. All private API, action and report responses require private, no-store. Production page-header behavior is not certified here.',
    total: checks.length, passed: checks.length - failed.length, failed: failed.length, checks,
  };
  const directory = path.join(__dirname, '../acceptance/clerk');
  await fs.mkdir(directory, { recursive: true });
  await fs.writeFile(path.join(directory, 'http-smoke.json'), JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify(result));
  if (failed.length) process.exitCode = 1;
}

main().catch(error => {
  console.error(error instanceof SmokeError ? error.message : 'HTTP verification could not complete. No credentials or response bodies were recorded.');
  process.exitCode = 1;
});
