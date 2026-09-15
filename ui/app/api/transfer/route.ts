import {allowedOrigin, backendConfig, conversationId, ROLES, type Role} from '../../../lib/backend';

export const runtime = 'nodejs';

export async function POST(request: Request) {
  if (!allowedOrigin(request)) return new Response('Forbidden', {status: 403});
  let body: Record<string, unknown>;
  try {
    body = await request.json();
  } catch {
    return new Response('Invalid JSON', {status: 400});
  }
  const sourceRole = body.source_role;
  const targetRole = body.target_role;
  if (!ROLES.includes(sourceRole as Role) || !ROLES.includes(targetRole as Role)) {
    return new Response('Invalid role', {status: 400});
  }
  if (sourceRole === targetRole) return new Response('Source and target must differ', {status: 400});
  const sourceThread = String(body.source_thread_id || '');
  const targetThread = String(body.target_thread_id || '');
  if (!conversationId.test(sourceThread) || !conversationId.test(targetThread)) {
    return new Response('Invalid conversation', {status: 400});
  }
  const messageIds = Array.isArray(body.message_ids) ? body.message_ids.map(String) : [];
  try {
    const {url, token} = backendConfig(sourceRole as Role);
    const response = await fetch(url + '/transfer', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        source_role: sourceRole,
        source_thread_id: sourceThread,
        target_role: targetRole,
        target_thread_id: targetThread,
        message_ids: messageIds,
      }),
      signal: AbortSignal.timeout(10000),
    });
    if (!response.ok) {
      const text = await response.text().catch(() => 'Transfer unavailable');
      return new Response(text, {
        status: response.status,
        headers: {'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store'},
      });
    }
    return Response.json(await response.json(), {headers: {'Cache-Control': 'no-store'}});
  } catch {
    return new Response('Transfer unavailable', {status: 503});
  }
}
