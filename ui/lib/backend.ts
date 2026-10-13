import {readFileSync} from 'node:fs';

export const conversationId = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function backendConfig(env: Record<string, string | undefined> = process.env) {
  const url = new URL(env.NORA_COORDINATION_URL?.trim() || 'http://coordination:8000');
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
    throw new Error('Invalid Coordination URL');
  }
  const direct = env.NORA_INTERNAL_TOKEN?.trim();
  const file = env.NORA_INTERNAL_TOKEN_FILE;
  if (direct && file) throw new Error('Configure one internal credential source');
  const token = direct || (file ? readFileSync(file, 'utf8').trim() : '');
  if (!token || /[\r\n\0]/.test(token)) throw new Error('Configure the internal credential');
  return {url: url.toString().replace(/\/$/, ''), token};
}

export function allowedOrigin(request: Request, env: Record<string, string | undefined> = process.env): boolean {
  const origin = request.headers.get('origin');
  if (!origin) return true;
  const allowed = (env.NORA_UI_ALLOWED_ORIGINS || 'http://localhost:8080,http://127.0.0.1:8080')
    .split(',').map(value => value.trim());
  if (allowed.includes(origin)) return true;
  try {
    const source = new URL(origin);
    const internal = new URL(request.url);
    return ['localhost', '127.0.0.1'].includes(source.hostname)
      && source.protocol === internal.protocol
      && source.host === (request.headers.get('host') || internal.host);
  } catch { return false; }
}

export async function backendFetch(path: string, request?: Request, timeout = 5000) {
  const {url, token} = backendConfig();
  const signals = [AbortSignal.timeout(timeout)];
  if (request) signals.push(request.signal);
  return fetch(url + path, {headers: {Authorization: `Bearer ${token}`},
    cache: 'no-store', signal: AbortSignal.any(signals)});
}

export async function boundedBody(request: Request, limit = 70000): Promise<Uint8Array> {
  if (Number(request.headers.get('content-length')) > limit) throw new RangeError('Request too large');
  const reader = request.body?.getReader();
  if (!reader) return new Uint8Array();
  const chunks: Uint8Array[] = [];
  let length = 0;
  try {
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      length += value.length;
      if (length > limit) throw new RangeError('Request too large');
      chunks.push(value);
    }
  } catch (error) {
    await reader.cancel();
    throw error;
  } finally {
    reader.releaseLock();
  }
  const bytes = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  return bytes;
}
