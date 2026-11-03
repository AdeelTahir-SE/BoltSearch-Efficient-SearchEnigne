import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const envPath = fileURLToPath(new URL('../.env', import.meta.url));
if (existsSync(envPath)) {
  if (!process.loadEnvFile) throw new Error('Use Node.js 20.12+ to load server/.env.');
  process.loadEnvFile(envPath);
}
