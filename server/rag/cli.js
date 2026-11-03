import '../express/env.js';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const command = process.argv[2] || 'status';
if (command === 'embed-all') {
  // Foreground resumes use the same supervisor/progress metadata as hidden jobs.
  await import('./background.js');
} else {
  const child = spawn(process.env.PYTHON || 'python', [fileURLToPath(new URL('./worker.py', import.meta.url)), command, '--cli'], {
    stdio: 'inherit', windowsHide: true,
  });
  child.on('error', () => { console.error('Could not start Python. Check PYTHON in server/.env.'); process.exitCode = 1; });
  child.on('exit', code => { process.exitCode = code ?? 1; });
}
