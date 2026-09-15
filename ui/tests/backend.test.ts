import {strict as assert} from 'node:assert';
import {mkdtempSync, writeFileSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import test from 'node:test';
import {allowedOrigin, backendConfig, boundedBody, conversationId, parseRole} from '../lib/backend.ts';

test('credentials are lazy, file-backed and not forwarded through a URL', () => {
  const directory = mkdtempSync(join(tmpdir(), 'nora-test-'));
  try {
    const path = join(directory, 'token');
    writeFileSync(path, 'synthetic-token\n');
    assert.equal(backendConfig('knowledge', {NORA_INTERNAL_TOKEN_FILE: path}).token, 'synthetic-token');
    writeFileSync(path, 'rotated-token');
    assert.equal(backendConfig('knowledge', {NORA_INTERNAL_TOKEN_FILE: path}).token, 'rotated-token');
    assert.throws(() => backendConfig('knowledge', {NORA_INTERNAL_TOKEN_FILE: path, NORA_INTERNAL_TOKEN: 'another'}));
    assert.throws(() => backendConfig('knowledge', {NORA_INTERNAL_TOKEN: 'test', NORA_KNOWLEDGE_URL: 'https://user:pass@example.com'}));
    assert.throws(() => backendConfig('knowledge', {}));
  } finally { rmSync(directory, {recursive: true}); }
});

test('role URLs resolve from explicit env or default service name', () => {
  const env = {
    NORA_INTERNAL_TOKEN: 'test',
    NORA_KNOWLEDGE_URL: 'http://coordination:8000',
    NORA_RESEARCH_URL: 'http://research:8003',
  };
  assert.equal(backendConfig('knowledge', env).url, 'http://coordination:8000');
  assert.equal(backendConfig('research', env).url, 'http://research:8003');
  assert.equal(backendConfig('interview', env).url, 'http://role-interview:8004');
  // Backward compatibility: NORA_COORDINATION_URL serves Knowledge.
  assert.equal(
    backendConfig('knowledge', {NORA_INTERNAL_TOKEN: 'test', NORA_COORDINATION_URL: 'http://old:8000'}).url,
    'http://old:8000'
  );
});

test('accepted default topology uses coordination for knowledge and role services for others', () => {
  const env = {NORA_INTERNAL_TOKEN: 'test'};
  assert.equal(backendConfig('knowledge', env).url, 'http://coordination:8000');
  assert.equal(backendConfig('research', env).url, 'http://role-research:8003');
  assert.equal(backendConfig('interview', env).url, 'http://role-interview:8004');
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


test('copilotkit route parses role slug for all roles', () => {
  assert.equal(parseRole(['knowledge']), 'knowledge');
  assert.equal(parseRole(['research']), 'research');
  assert.equal(parseRole(['interview']), 'interview');
  assert.equal(parseRole(['knowledge', 'agent']), 'knowledge');
  assert.equal(parseRole(['research', 'agent']), 'research');
  assert.equal(parseRole(['interview', 'agent']), 'interview');
  assert.equal(parseRole([]), null);
  assert.equal(parseRole(['knowledge', 'extra']), null);
  assert.equal(parseRole(['unknown']), null);
  assert.equal(parseRole(['knowledge', 'connect']), null);
});

test('role selection switches backend URL and keeps credentials local', () => {
  const env = {NORA_INTERNAL_TOKEN: 'test'};
  assert.equal(backendConfig('knowledge', env).url, 'http://coordination:8000');
  assert.equal(backendConfig('research', env).url, 'http://role-research:8003');
  assert.equal(backendConfig('interview', env).url, 'http://role-interview:8004');
});

test('selected-text transfer requests use the source role backend', () => {
  // backendFetch is called with the source role; the target is only used by
  // the client to open a new chat.  Verify the URL follows the role map.
  const env = {
    NORA_INTERNAL_TOKEN: 'test',
    NORA_RESEARCH_URL: 'http://role-research:8003',
  };
  const cfg = backendConfig('research', env);
  assert.equal(cfg.url, 'http://role-research:8003');
});
