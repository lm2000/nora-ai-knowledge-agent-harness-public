import {allowedOrigin, backendFetch, conversationId} from '../../../../lib/backend';

export const runtime = 'nodejs';

export async function GET(request: Request, context: {params: Promise<{role: string}>}) {
  if (!allowedOrigin(request)) return new Response('Forbidden', {status: 403});
  const {role} = await context.params;
  // Backward-compatible single-role alias: this segment is named `role` so
  // Next.js allows the sibling `[role]/[thread]` route, but it is interpreted
  // as the client-visible conversation id and routed to the Knowledge backend.
  if (!conversationId.test(role)) return new Response('Invalid conversation', {status: 400});
  try {
    const result = await backendFetch('knowledge', '/history/knowledge/' + role, request);
    if (!result.ok) throw new Error('History unavailable');
    return new Response(await result.text(), {headers: {'Content-Type': 'application/json', 'Cache-Control': 'no-store'}});
  } catch {
    return new Response('Conversation unavailable', {status: 503});
  }
}
