import { createServer } from 'node:http';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { experimental_evaluate as evaluate } from 'ai';
import { createGateway } from '@ai-sdk/gateway';

type Input = Pick<Parameters<typeof evaluate>[0], 'state' | 'questions'> & { model: string };
export async function convert(input: Input, run = evaluate) {
  const model = process.env.JEV_MODEL || 'typesafe-ai/jev';
  if (input.model !== model) throw new Error('Unexpected evaluation model');
  const apiKey = process.env.AI_GATEWAY_API_KEY || (process.env.AI_GATEWAY_API_KEY_FILE
    ? readFileSync(process.env.AI_GATEWAY_API_KEY_FILE, 'utf8').trim() : '');
  if (!apiKey) throw new Error('AI_GATEWAY_API_KEY is required');
  const gateway = createGateway({ apiKey });
  const result = await run({
    model: gateway.evaluationModel(model), state: input.state, questions: input.questions,
    maxRetries: 0, abortSignal: AbortSignal.timeout(20_000),
    providerOptions: { gateway: { tags: ['app:jev-ultrafast', 'host:nas', 'component:decision'] } },
  });
  // Gateway omits TypeSafe's confidence field. Use the selected option probability,
  // without inventing missing probabilities or changing any selected choice.
  const answers = Object.fromEntries(Object.entries(result.answers).map(([id, answer]) => [id,
    answer.type === 'choice' ? { ...answer, confidence: answer.probabilities?.[answer.choice] } : answer,
  ]));
  return { model, answers, usage: result.usage };
}

export function server() {
  const http = createServer(async (req, res) => {
    const send = (status: number, value: object) => {
      res.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
      res.end(JSON.stringify(value));
    };
    if (req.method === 'GET' && req.url === '/healthz') return send(200, { status: 'ok' });
    // No browser-facing API and no published port. Reject browser-originated requests.
    if (req.headers.origin) return send(403, { error: 'Forbidden' });
    if (req.method !== 'POST' || req.url !== '/evaluate') return send(404, { error: 'Not found' });
    let size = 0;
    const chunks: Buffer[] = [];
    try {
      for await (const chunk of req) {
        size += chunk.length;
        if (size > 1_048_576) return send(413, { error: 'Request too large' });
        chunks.push(chunk);
      }
      let input: Input;
      try { input = JSON.parse(Buffer.concat(chunks).toString()); }
      catch { return send(400, { error: 'Invalid JSON' }); }
      const result = await convert(input);
      console.info(JSON.stringify({ component: 'decision', provider: 'vercel', model: result.model,
        status: 'ok', usage: result.usage }));
      send(200, result);
    } catch {
      // SDK errors can include request bodies/credentials. Never log them.
      console.error(JSON.stringify({ component: 'decision', provider: 'vercel', status: 'failed' }));
      send(502, { error: 'Gateway evaluation failed; no direct-provider fallback' });
    }
  });
  http.requestTimeout = 30_000;
  http.headersTimeout = 10_000;
  return http;
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const http = server().listen(Number(process.env.PORT || 8767), '0.0.0.0');
  process.on('SIGTERM', () => http.close(() => process.exit(0)));
}
