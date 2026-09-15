import {allowedOrigin, backendFetch} from '../../../lib/backend';

export const runtime = 'nodejs';

export async function GET(request: Request) {
  if (!allowedOrigin(request)) return new Response('Forbidden', {status: 403});
  try {
    const response = await backendFetch('knowledge', '/health', request, 3000);
    if (!response.ok) throw new Error('Backend is not ready');
    const health = await response.json();
    const documents = Number.isSafeInteger(health.documents) && health.documents >= 0 ? health.documents : 0;
    return Response.json({ready: true, documents, label: `${documents.toLocaleString()} prepared documents`},
      {headers: {'Cache-Control': 'no-store'}});
  } catch {
    return Response.json({label: 'Nora is unavailable', ready: false}, {status: 503});
  }
}
