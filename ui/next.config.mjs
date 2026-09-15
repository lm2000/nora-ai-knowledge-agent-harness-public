import path from 'node:path';
import {fileURLToPath} from 'node:url';
export default {output:'standalone',poweredByHeader:false,turbopack:{root:path.dirname(fileURLToPath(import.meta.url))}};
