import {spawn} from "child_process"
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';

export async function uploadDocument(filePath) {
  const __filename = fileURLToPath(import.meta.url);
  const __dirname = dirname(__filename);
  
  // Resolve the absolute path of the Python script
  const scriptPath = resolve(__dirname, '../../server/file-upload/uploadFile.py'); // Adjust path as needed
  const pythonProcess = spawn("python", [scriptPath,filePath]);

    pythonProcess.stdout.on("data", (data) => {
      console.log(`Output: ${data.toString()}`);
    });
    
    pythonProcess.stderr.on("data", (data) => {
      console.error(`Error: ${data.toString()}`);
    });
    
    pythonProcess.on("close", (code) => {
      console.log(`Python script exited with code ${code}`);
    });

}
        
export async function searchDocuments(words){
    const scriptPath="../search-query/searchDocuments.py"
    const args=words;
    const pythonProcess = spawn("python", [scriptPath, ...args]);

pythonProcess.stdout.on("data", (data) => {
  console.log(`Output: ${data.toString()}`);
});

pythonProcess.stderr.on("data", (data) => {
  console.error(`Error: ${data.toString()}`);
});

pythonProcess.on("close", (code) => {
  console.log(`Python script exited with code ${code}`);
});
}
