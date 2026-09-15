import {CopilotRuntime, createCopilotRuntimeHandler} from '@copilotkit/runtime/v2';
import {LangGraphHttpAgent} from '@copilotkit/runtime/langgraph';
import {allowedOrigin, backendConfig, backendFetch, boundedBody, conversationId, ROLES, type Role} from '../../../../lib/backend';

export const runtime = 'nodejs';

function createHandler(role: Role) {
  const {url, token} = backendConfig(role);
  const copilotRuntime = new CopilotRuntime({agents: {[role]: new LangGraphHttpAgent({
    url: url + '/agent', headers: {Authorization: `Bearer ${token}`, 'X-Nora-Role': role},
  })}});
  return createCopilotRuntimeHandler({runtime: copilotRuntime, basePath: `/api/copilotkit/${role}`});
}

async function handle(request: Request) {
  if (!allowedOrigin(request)) return new Response('Forbidden', {status: 403});
  const pathname = new URL(request.url).pathname;
  const segments = pathname.replace(/^\/api\/copilotkit\/?/, '').split('/').filter(Boolean);
  const role = segments[0] && ROLES.includes(segments[0] as Role) ? (segments[0] as Role) : null;
  if (!role) return new Response('Invalid role', {status: 400});
  try {
    if (request.method === 'POST' && pathname.endsWith(`/agent/${role}/connect`)) {
      const bytes = await boundedBody(request);
      const text = new TextDecoder().decode(bytes);
      const data = JSON.parse(text);
      if (typeof data.threadId !== 'string' || !conversationId.test(data.threadId)) {
        return new Response('Invalid conversation', {status: 400});
      }
      let messages: unknown[] = [];
      try {
        const saved = await backendFetch(role, '/history/' + role + '/' + data.threadId, request);
        if (saved.ok) {
          const history = await saved.json() as {messages?: unknown[]};
          messages = history.messages || [];
        }
      } catch {
        /* New threads have no backend owner yet; start with an empty history. */
      }
      const runId = typeof data.runId === 'string' ? data.runId : crypto.randomUUID();
      const events = [
        {type: 'RUN_STARTED', threadId: data.threadId, runId},
        {type: 'MESSAGES_SNAPSHOT', messages},
        {type: 'RUN_FINISHED', threadId: data.threadId, runId, outcome: {status: 'success'}},
      ];
      return new Response(events.map(event => 'data: ' + JSON.stringify(event) + '\n\n').join(''),
        {headers: {'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache'}});
    }
    if (request.method === 'POST') {
      const bytes = await boundedBody(request);
      const text = new TextDecoder().decode(bytes);
      request = new Request(request.url, {method: request.method, headers: request.headers,
        body: text, signal: request.signal});
    }
    return await createHandler(role)(request);
  } catch (error) {
    if (error instanceof RangeError) return new Response('Request too large', {status: 413});
    if (error instanceof SyntaxError) return new Response('Invalid JSON', {status: 400});
    return new Response('Nora is unavailable. Please retry.', {status: 503});
  }
}

export const GET = handle;
export const POST = handle;
