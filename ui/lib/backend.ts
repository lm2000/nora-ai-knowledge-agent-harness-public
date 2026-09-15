import {readFileSync} from 'node:fs';

export const conversationId = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const ROLES = ['knowledge', 'research', 'interview'] as const;
export type Role = typeof ROLES[number];

export function parseRole(slug: string[]): Role | null {
  if (slug.length === 1 && ROLES.includes(slug[0] as Role)) return slug[0] as Role;
  if (slug.length === 2 && slug[1] === 'agent' && ROLES.includes(slug[0] as Role)) return slug[0] as Role;
  return null;
}

const ROLE_PORTS: Record<Role, number> = {
  knowledge: 8000,
  research: 8003,
  interview: 8004,
};

function roleUrl(role: Role, env: Record<string, string | undefined>): string {
  const direct = env[`NORA_${role.toUpperCase()}_URL`]?.trim();
  if (direct) {
    const url = new URL(direct);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
      throw new Error(`Invalid ${role} role URL`);
    }
    return url.toString().replace(/\/$/, '');
  }
  const base = env.NORA_COORDINATION_URL?.trim();
  if (base) {
    const url = new URL(base);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
      throw new Error('Invalid Coordination URL');
    }
    return url.toString().replace(/\/$/, '');
  }
  // Accepted default topology: existing coordination service serves Knowledge,
  // dedicated role runtimes serve Research and Interview.
  return role === 'knowledge'
    ? `http://coordination:${ROLE_PORTS[role]}`
    : `http://role-${role}:${ROLE_PORTS[role]}`;
}

export function backendConfig(role: Role, env: Record<string, string | undefined> = process.env) {
  const url = roleUrl(role, env);
  const direct = env.NORA_INTERNAL_TOKEN?.trim();
  const file = env.NORA_INTERNAL_TOKEN_FILE;
  if (direct && file) throw new Error('Configure one internal credential source');
  const token = direct || (file ? readFileSync(file, 'utf8').trim() : '');
  if (!token || /[\r\n\0]/.test(token)) throw new Error('Configure the internal credential');
  return {url, token};
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

export async function backendFetch(role: Role, path: string, request?: Request, timeout = 5000) {
  const {url, token} = backendConfig(role);
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
