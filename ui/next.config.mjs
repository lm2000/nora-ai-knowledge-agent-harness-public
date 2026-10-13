import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root = path.dirname(fileURLToPath(import.meta.url));
export default {
  output: 'standalone',
  poweredByHeader: false,
  outputFileTracingRoot: process.env.NORA_UI_TRACING_ROOT || root,
  turbopack: {root: process.env.NORA_UI_TRACING_ROOT || root},
};
