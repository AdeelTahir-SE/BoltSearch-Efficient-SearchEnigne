import child_process from 'child_process';
import {spawn} from "child_process"
export async function uploadDocument(filePath) {
    const scriptPath="../file-upload/uploadFile.py"
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
