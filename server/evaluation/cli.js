import '../express/env.js';
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

process.env.RAGAS_DO_NOT_TRACK = 'true';
process.env.HF_HUB_DISABLE_TELEMETRY = '1';
process.env.DO_NOT_TRACK = '1';
const python = fileURLToPath(new URL(process.platform === 'win32' ? '../.venv-eval/Scripts/python.exe' : '../.venv-eval/bin/python', import.meta.url));
if (!existsSync(python)) {
  console.error('Create server/.venv-eval and install evaluation/requirements.txt first. See docs/EVALUATION.md.');
  process.exit(1);
}
const child = spawn(python, [fileURLToPath(new URL('./score.py', import.meta.url)), ...process.argv.slice(2)], { stdio: 'inherit', windowsHide: true });
child.on('error', () => { console.error('Could not start the evaluation environment.'); process.exitCode = 1; });
child.on('exit', code => { process.exitCode = code ?? 1; });
