import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { FaSearch, FaUpload } from 'react-icons/fa';

export default function App() {
  const [searchQuery, setSearchQuery] = useState('');
  const [jsonFile, setJsonFile] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedDocumentIndex, setSelectedDocumentIndex] = useState(null);

  const handleSearchChange = (event) => {
    setSearchQuery(event.target.value);
  };

  const handleFileChange = (event) => {
    const file = event.target.files[0];
    if (file && file.type === 'application/json') {
      setJsonFile(file);
    } else {
      alert('Please upload a valid JSON file.');
    }
  };

  const handleFileSubmission = async () => {
    if (!jsonFile) {
      alert('Please select a file first.');
      return;
    }

    const formData = new FormData();
    formData.append('file', jsonFile);

    try {
      const response = await fetch('http://localhost:3000/api/documents', {
        method: 'POST',
        body: formData,
      });

      const result = await response.json();
      if(result.message){
      alert('File uploaded successfully.');
      }
      else{
        alert("Document with same Id already present")
      }
      setJsonFile(null);
    } catch (error) {
      console.error('Error uploading file:', error);
      alert('Failed to upload file.');
    }
  };

  const onDrop = useCallback((acceptedFiles) => {
    const file = acceptedFiles[0];
    if (file && file.type === 'application/json') {
      setJsonFile(file);
      console.log('File selected:', file);
    } else {
      alert('Please upload a valid JSON file.');
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop, accept: '.json' });

  const handleSearchSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);

    if (!searchQuery.trim()) {
      alert('Please enter a valid search query.');
      return;
    }

    try {
      const response = await fetch(`http://localhost:3000/api/documents?args=${encodeURIComponent(searchQuery)}`);
      if (!response.ok) {
        throw new Error('Failed to fetch documents.');
      }

      const result = await response.json();
      console.log(result); // Log to check the structure of the result
      if (Array.isArray(result) && result.length > 0) {
        setDocuments(result);
      } else {
        alert('No results found.');
        setDocuments([]); // Clear the documents if no results
      }
    } catch (error) {
      console.error('Error fetching search results:', error);
      alert('Failed to fetch documents.');
    } finally {
      setLoading(false);
    }
  };

  const toggleDocumentContent = (index) => {
    setSelectedDocumentIndex(selectedDocumentIndex === index ? null : index);
  };

  // Function to split the Answer by `,,,,,`
  const splitAnswer = (answer) => {
    if (!answer) return []; // Return empty array if no answer
    return answer.split(',,,,,').map((item, index) => (
      <li key={index}>{item.trim()}</li> // Trim each item and return as <li>
    ));
  };

  const renderAnswerAsHTML = (answer) => {
    if (!answer) return <p>No answer available</p>; // Handle no answer scenario
  
    return <div dangerouslySetInnerHTML={{ __html: answer }} />;
  };

  return (
    <section className="flex flex-col items-center justify-center min-h-screen">
      <header className="w-full text-white p-4 text-center">
        <h1 className="text-7xl font-bold text-transparent bg-clip-text bg-gradient-to-b from-white via-slate-400 to-slate-950">
          Bolt Search
        </h1>
      </header>

      <div className="container mx-auto p-4 flex flex-col items-center justify-center w-full max-w-4xl">
        <form onSubmit={handleSearchSubmit} className="mb-4 w-full max-w-md">
          <div className="flex items-center border-b-2 border-slate-500 py-2">
            <input
              type="text"
              value={searchQuery}
              onChange={handleSearchChange}
              placeholder="Enter search query"
              className="appearance-none bg-transparent border-none w-full text-gray-700 mr-3 py-1 px-2 leading-tight focus:outline-none"
            />
            <button
              type="submit"
              className="flex-shrink-0 bg-blue-500 hover:bg-blue-700 border-blue-500 hover:border-blue-700 text-sm border-4 text-white py-1 px-2 rounded"
            >
              <FaSearch />
            </button>
          </div>
        </form>

        {loading && <p className="text-black">Loading...</p>}
        {!loading && documents && documents.length > 0 ? (
          <div className="w-full p-4 mt-8 overflow-auto">
            <h2 className="text-2xl font-bold mb-4">Search Results</h2>
            <ul className="text-black">
              {documents.map((document, index) => (
                <li key={index} className="mb-2 text-3xl">
                  <h3
                    className="font-bold text-blue-500 underline cursor-pointer mt-2"
                    onClick={() => toggleDocumentContent(index)}
                  >
                    {index}- {document.Title || 'No Title Available'}
                  </h3>
                  {selectedDocumentIndex === index && (
                    <>
                    <h2 className='font-extrabold text-2xl'>Question:</h2>
                      <div
                        className="body-content"
                        dangerouslySetInnerHTML={{
                          __html: document.Body || 'No Body Available',
                        }}
                      />
                      <div className="answer-content mt-4">
                      <h2 className='font-extrabold text-2xl'>Answers:</h2>
                      <ul>
                      <div>
                      {renderAnswerAsHTML(document.Answer)}
                      </div> 
                       </ul>
                      </div>
                    </>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <div className="mt-8 text-white">
            <p>No results to display.</p>
          </div>
        )}

        <div className="upload-section mt-8 w-full max-w-md">
          <h2 className="text-2xl font-bold mb-2">Upload JSON File</h2>
          <div className="flex items-center">
            <input
              type="file"
              name="file"
              accept=".json"
              onChange={handleFileChange}
              className="appearance-none bg-transparent border-none w-full text-gray-700 mr-3 py-1 px-2 leading-tight focus:outline-none"
            />
            <button
              className="flex-shrink-0 bg-blue-500 hover:bg-blue-700 border-blue-500 hover:border-blue-700 text-sm border-4 text-white py-1 px-2 rounded"
              onClick={handleFileSubmission}
            >
              <FaUpload />
            </button>
          </div>
          {jsonFile && <p className="mt-2 text-blue-600">Uploaded: {jsonFile.name}</p>}
        </div>

        <div
          {...getRootProps()}
          className="dropzone mt-8 w-full max-w-md p-4 border-2 border-dashed border-blue-500 rounded-md text-center"
        >
          <input {...getInputProps()} />
          {isDragActive ? (
            <p className="text-blue-500">Drop the files here ...</p>
          ) : (
            <p className="text-gray-700">Drag 'n' drop a JSON file here, or click to select one</p>
          )}
        </div>
      </div>

      <footer className="w-full text-white p-4 text-center mt-8">
        <p>&copy; 2024 Bolt Search. All rights reserved.</p>
      </footer>
    </section>
  );
}
