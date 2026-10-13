import {strict as assert} from 'node:assert';
import {mkdtempSync, writeFileSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import test from 'node:test';
import {allowedOrigin, backendConfig, boundedBody, conversationId, backendFetch} from '../lib/backend.ts';

test('credentials are lazy, file-backed and not forwarded through a URL', () => {
  const directory = mkdtempSync(join(tmpdir(), 'nora-test-'));
  try {
    const path = join(directory, 'token');
    writeFileSync(path, 'synthetic-token\n');
    assert.equal(backendConfig({NORA_INTERNAL_TOKEN_FILE: path}).token, 'synthetic-token');
    writeFileSync(path, 'rotated-token');
    assert.equal(backendConfig({NORA_INTERNAL_TOKEN_FILE: path}).token, 'rotated-token');
    assert.throws(() => backendConfig({NORA_INTERNAL_TOKEN_FILE: path, NORA_INTERNAL_TOKEN: 'another'}));
    assert.throws(() => backendConfig({NORA_INTERNAL_TOKEN: 'test', NORA_COORDINATION_URL: 'https://user:pass@example.com'}));
    assert.throws(() => backendConfig({}));
  } finally { rmSync(directory, {recursive: true}); }
});

test('one Coordination URL is explicit or defaults to the service', () => {
  assert.equal(backendConfig({NORA_INTERNAL_TOKEN: 'test'}).url, 'http://coordination:8000');
  assert.equal(backendConfig({NORA_INTERNAL_TOKEN: 'test', NORA_COORDINATION_URL: 'https://example.com/'}).url, 'https://example.com');
  for (const url of ['ftp://example.com', 'https://user:pass@example.com', 'http://example.com?token=x', 'http://example.com#fragment']) {
    assert.throws(() => backendConfig({NORA_INTERNAL_TOKEN: 'test', NORA_COORDINATION_URL: url}));
  }
});

test('origins and conversation IDs are checked', () => {
  assert.equal(allowedOrigin(new Request('http://localhost:8080/api', {headers: {origin: 'http://other.example'}})), false);
  assert.equal(allowedOrigin(new Request('http://localhost:8080/api', {headers: {origin: 'http://localhost:8080'}})), true);
  assert.equal(allowedOrigin(new Request('http://0.0.0.0:3000/api', {headers: {origin: 'http://127.0.0.1:3000', host: '127.0.0.1:3000'}})), true);
  assert.equal(allowedOrigin(new Request('http://0.0.0.0:3000/api', {headers: {origin: 'http://rebinding.example:3000', host: 'rebinding.example:3000'}})), false);
  assert.equal(conversationId.test(crypto.randomUUID()), true);
  assert.equal(conversationId.test('../other'), false);
});

test('body limit applies without a content-length header', async () => {
  const small = new Request('http://localhost', {method: 'POST', body: 'hello'});
  assert.equal(new TextDecoder().decode(await boundedBody(small)), 'hello');
  const large = new Request('http://localhost', {method: 'POST', body: 'x'.repeat(70001)});
  await assert.rejects(boundedBody(large), RangeError);
});


test('backend requests carry server credential and use the single backend', async () => {
  const originalFetch = globalThis.fetch;
  const priorToken = process.env.NORA_INTERNAL_TOKEN;
  const priorURL = process.env.NORA_COORDINATION_URL;
  process.env.NORA_INTERNAL_TOKEN = 'synthetic-token';
  process.env.NORA_COORDINATION_URL = 'http://coordination:8000';
  try {
    globalThis.fetch = async (url, options) => {
      assert.equal(url, 'http://coordination:8000/history/11111111-1111-4111-8111-111111111111');
      assert.equal((options?.headers as Record<string, string>).Authorization, 'Bearer synthetic-token');
      assert.equal(options?.cache, 'no-store');
      return Response.json({messages: []});
    };
    assert.equal((await backendFetch('/history/11111111-1111-4111-8111-111111111111')).status, 200);
  } finally {
    globalThis.fetch = originalFetch;
    if (priorToken === undefined) delete process.env.NORA_INTERNAL_TOKEN; else process.env.NORA_INTERNAL_TOKEN = priorToken;
    if (priorURL === undefined) delete process.env.NORA_COORDINATION_URL; else process.env.NORA_COORDINATION_URL = priorURL;
  }
});
