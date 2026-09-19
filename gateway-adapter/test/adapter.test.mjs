import { test } from 'node:test';
import assert from 'node:assert/strict';
import { convert, server } from '../dist/server.js';

const input = { model: 'typesafe-ai/jev', state: { page: 'test' }, questions: {
  operation: { type: 'choice', instructions: { goal: 'test' }, criteria: { CLICK: {}, DONE: 'finished' } },
} };
test('real SDK serializes evaluation protocol and converts probabilities without chat', async () => {
  const original = globalThis.fetch;
  process.env.AI_GATEWAY_API_KEY = 'offline-test-key';
  let calls = 0;
  globalThis.fetch = async (url, init) => {
    calls++;
    assert.match(String(url), /^https:\/\/ai-gateway.vercel.sh\/.*evaluation-model$/);
    const headers = new Headers(init.headers);
    assert.equal(headers.get('ai-model-id'), input.model);
    assert.equal(headers.get('ai-evaluation-model-specification-version'), '4');
    const body = JSON.parse(init.body);
    assert.deepEqual(body.questions, input.questions);
    assert.deepEqual(body.state, input.state);
    assert.deepEqual(body.providerOptions.gateway.tags, ['app:jev-ultrafast', 'host:nas', 'component:decision']);
    return Response.json({ answers: { operation: { type: 'choice', choice: 'CLICK',
      probabilities: { CLICK: 0.9, DONE: 0.1 } } }, usage: { inputTokens: 10, outputTokens: 1 } });
  };
  try {
    const result = await convert(input);
    assert.equal(result.answers.operation.confidence, 0.9);
    assert.equal(calls, 1);
  } finally { globalThis.fetch = original; delete process.env.AI_GATEWAY_API_KEY; }
});
test('missing key and wrong model fail closed', async () => {
  delete process.env.AI_GATEWAY_API_KEY;
  delete process.env.AI_GATEWAY_API_KEY_FILE;
  await assert.rejects(convert(input), /API_KEY/);
  await assert.rejects(convert({ ...input, model: 'other' }), /Unexpected/);
});
test('HTTP health, browser origin rejection and malformed JSON', async () => {
  const http = server().listen(0, '127.0.0.1');
  await new Promise(resolve => http.once('listening', resolve));
  const url = `http://127.0.0.1:${http.address().port}`;
  try {
    assert.equal((await fetch(url + '/healthz')).status, 200);
    assert.equal((await fetch(url + '/evaluate', { method: 'POST', headers: { Origin: 'https://evil.test' } })).status, 403);
    assert.equal((await fetch(url + '/evaluate', { method: 'POST', body: '{' })).status, 400);
  } finally { await new Promise(resolve => http.close(resolve)); }
});
test('Gateway failure makes one SDK attempt and never calls direct TypeSafe', async () => {
  const original = globalThis.fetch;
  process.env.AI_GATEWAY_API_KEY = 'offline-test-key';
  let calls = 0;
  globalThis.fetch = async (url) => {
    calls++;
    assert.equal(new URL(url).hostname, 'ai-gateway.vercel.sh');
    return Response.json({ error: 'unavailable' }, { status: 503 });
  };
  try { await assert.rejects(convert(input)); assert.equal(calls, 1); }
  finally { globalThis.fetch = original; delete process.env.AI_GATEWAY_API_KEY; }
});
