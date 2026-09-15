import {allowedOrigin, backendFetch, conversationId, ROLES, type Role} from '../../../../../lib/backend';

export const runtime = 'nodejs';

export async function GET(
  request: Request,
  context: {params: Promise<{role: string; thread: string}>}
) {
  if (!allowedOrigin(request)) return new Response('Forbidden', {status: 403});
  const {role, thread} = await context.params;
  if (!ROLES.includes(role as Role)) return new Response('Invalid role', {status: 400});
  if (!conversationId.test(thread)) return new Response('Invalid conversation', {status: 400});
  try {
    const result = await backendFetch(role as Role, '/history/' + role + '/' + thread, request);
    if (!result.ok) throw new Error('History unavailable');
    return new Response(await result.text(), {headers: {'Content-Type': 'application/json', 'Cache-Control': 'no-store'}});
  } catch {
    return new Response('Conversation unavailable', {status: 503});
  }
}
