import {allowedOrigin, backendFetch, conversationId} from '../../../../lib/backend';

export const runtime = 'nodejs';

export async function GET(request: Request, context: {params: Promise<{thread_id: string}>}) {
  if (!allowedOrigin(request)) return new Response('Forbidden', {status: 403});
  const {thread_id} = await context.params;
  if (!conversationId.test(thread_id)) return new Response('Invalid conversation', {status: 400});
  try {
    const result = await backendFetch('/history/' + thread_id, request);
    if (!result.ok) throw new Error('History unavailable');
    return new Response(await result.text(), {headers: {'Content-Type': 'application/json', 'Cache-Control': 'no-store'}});
  } catch {
    return new Response('Conversation unavailable', {status: 503});
  }
}
