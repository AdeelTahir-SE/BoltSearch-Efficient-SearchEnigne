import {spawn} from "child_process"
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';
import fse from "fs-extra"

export async function uploadDocument(filePath) {
  const __filename = fileURLToPath(import.meta.url);
  const __dirname = dirname(__filename);
  
  // Resolve the absolute path of the Python script
  const scriptPath = resolve(__dirname, '../../server/file-upload/uploadFile.py'); // Adjust path as needed
  console.log("Running Python script:", scriptPath, " with file:", filePath);
  
  // Use a promise to wrap the Python script execution
  return new Promise((resolve, reject) => {
    const pythonProcess = spawn("python", [scriptPath, filePath]);

    pythonProcess.stdout.on("data", (data) => {
      console.log(`Output: ${data.toString()}`);
    });

    pythonProcess.stderr.on("data", (data) => {
      console.error(`Error: ${data.toString()}`);
    });

    pythonProcess.on("close", (code) => {
      if (code === 0) {
        console.log(`Python script completed successfully with code ${code}`);
        resolve(code); // Resolve the promise on success
      } else {
        console.error(`Python script exited with code ${code}`);
        reject(`Python script failed with code ${code}`); // Reject the promise on failure
      }
    });
  });
}


export function searchDocuments(args, limit) {
  return new Promise((resolve, reject) => {
    const words = args.split(" ");

    // Run the Python script for each word in parallel
    const promises = words.map((word) => runPythonScript(word, limit));

    // Wait for all promises to resolve or reject
    Promise.all(promises)
      .then(async(results) => {
        // After getting results, slice the first `limit` documents
        const docs = results.slice(0, limit);
        const sortedResults = mergeAndPrioritizeResults(docs, limit); // Pass limit to merge function
        await fse.writeJSON('./results.json', sortedResults, { spaces: 2 });

        resolve(sortedResults);
      })
      .catch((error) => {
        reject(`Error executing Python script: ${error}`);
      });
  });
}

function mergeAndPrioritizeResults(resultsArray, limit) {
  const mergedResults = {};

  // Aggregate results and count occurrences
  resultsArray.forEach((results) => {
    results.forEach((doc) => {
      const docId = doc.Id;
      if (!mergedResults[docId]) {
        mergedResults[docId] = { ...doc, occurrence: 1 };
      } else {
        mergedResults[docId].occurrence += 1;
        mergedResults[docId].Score += doc.Score; // Adjust if needed
      }
    });
  });

  // Convert to array and sort
  const sortedResults = Object.values(mergedResults).sort((a, b) => {
    // Primary: Sort by occurrences
    if (b.occurrence !== a.occurrence) {
      return b.occurrence - a.occurrence;
    }

    // Secondary: Sort by Score
    if (b.Score !== a.Score) {
      return b.Score - a.Score;
    }
    if(b.CreationDate !== a.CreationDate){
    const dateA = new Date(a.CreationDate);
    const dateB = new Date(b.CreationDate);
    return dateB - dateA;
    }
  });

  return sortedResults.slice(0, limit);
}


function runPythonScript(word,limit) {
  return new Promise((resolve, reject) => {
    const pythonProcess = spawn("python", ["./search-query/searchDos.py", word,limit]);
    
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
          // Parse JSON output
          const results = JSON.parse(output.trim());
          resolve(results);
        } catch (error) {
          reject(`Failed to parse Python script output for word "${word}": ${error}`);
        }
      } else {
        reject(`Python script exited with code ${code} for word "${word}": ${errorOutput}`);
      }
    });
  });
}
