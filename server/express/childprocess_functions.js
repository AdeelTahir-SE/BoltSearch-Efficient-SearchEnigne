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
        

export function searchDocuments(args) {
  return new Promise((resolve, reject) => {
    const pythonProcess = spawn("python", ["./search-query/searchDos.py", ...args]);

    let output = "";
    let errorOutput = "";

    pythonProcess.stdout.on("data", (data) => {
      output += data.toString();
    });

    pythonProcess.stderr.on("data", (data) => {
      errorOutput += data.toString();
    });

    pythonProcess.on("close", (code) => {
      if (code === 0) {
        try {
          // Parse JSON output from Python script
          const results = JSON.parse(output.trim());
          console.log(results)
          resolve(results);
        } catch (error) {
          reject(`Failed to parse Python script output: ${error}`);
        }
      } else {
        reject(`Python script exited with code ${code}: ${errorOutput}`);
      }
    });
  });
}


