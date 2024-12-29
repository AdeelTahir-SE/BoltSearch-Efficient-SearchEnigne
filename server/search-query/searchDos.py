import sys
import os
import pandas as pd
from collections import defaultdict
import json
import documents_parser as dp

# Add the '../lemmatizer' folder to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lemmatizer'))

# Import custom lemmatizer functions
from lemmatizerfunctions import lemmatize_word, wordToken

def searchWord():
    try:
        word = sys.argv[1]
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 30  # Default to 30 if no limit is provided

        # Step 1: Lemmatize and tokenize the word
        lemmatized_word = lemmatize_word(word)
        token = wordToken(lemmatized_word)

        if not token:
            return json.dumps({"error": "Invalid token generated from the word."})

        # Step 2: Search for relevant token barrel files
        token_barrel_folder = './dataset/barrels'
        if not os.path.isdir(token_barrel_folder):
            return json.dumps({"error": f"Token barrel folder '{token_barrel_folder}' does not exist."})

        found_token_files = []
        for file in os.listdir(token_barrel_folder):
            if '-' in file:
                try:
                    # Extract start and end ranges, removing any extra spaces or file extensions
                    start, end = file.split('-')
                    start = start.strip().split('.')[0]  # Remove trailing file extensions, if any
                    end = end.strip().split('.')[0]

                    # Check if the token falls within the range
                    if int(start) <= int(token) <= int(end):
                        found_token_files.append(file)
                except ValueError:
                    pass  # Skip invalid files

        document_ids = []
        opened_files = {}  # Cache to store opened files and their data

        for file in found_token_files:
            file_path = os.path.join(token_barrel_folder, file)

            if os.path.isfile(file_path) and os.path.getsize(file_path) > 0:
                # Check if the file has already been opened and cached
                if file_path not in opened_files:
                    try:
                        # Read the CSV file and store its data in the cache
                        df = pd.read_csv(file_path)

                        # Create a dictionary for token lookups
                        token_dict = defaultdict(str)
                        for _, row in df.iterrows():
                            token_dict[str(row['Token_ID'])] = row['Document_IDs']

                        # Cache the token_dict for future use
                        opened_files[file_path] = token_dict
                    except Exception as e:
                        print(f"Error reading file {file_path}: {e}")  # Log the specific error for file reading
                        continue

                # Use the cached token_dict to search for tokens
                token_dict = opened_files[file_path]
                if token in token_dict:
                    document_ids.extend(token_dict[token].split(','))
                if f"{token}#" in token_dict:
                    document_ids.extend(token_dict[f"{token}#"].split(','))

        # Step 4: Search for documents in corresponding document barrels
        document_barrel_folder = './dataset/DocumentBarrels'
        if not os.path.isdir(document_barrel_folder):
            return json.dumps({"error": f"Document barrel folder '{document_barrel_folder}' does not exist."})

        results = []
        document_ids = list(set(document_ids))  # Remove duplicates
        document_ids = document_ids[:limit]  # Apply the limit

        if document_ids:
            for doc_id in document_ids:
                barrel_file = f"barrel_{(int(doc_id) // 4000) * 4000}_to_{(int(doc_id) // 4000) * 4000 + 3999}.csv"
                file_path = os.path.join(document_barrel_folder, barrel_file)

                if os.path.isfile(file_path) and os.path.getsize(file_path) > 0:
                    try:
                        # Read the document barrel file
                        df = pd.read_csv(file_path)

                        # Filter for the document ID
                        matching_docs = df[df['Id'] == int(doc_id)]
                        if not matching_docs.empty:
                            # Clean the data to remove NaN values
                            cleaned_docs = matching_docs.where(pd.notnull(matching_docs), None)
                            ranked_docs = dp.final_Documents(cleaned_docs)
                            results.extend(ranked_docs)  # Add results (list of dicts)

                    except Exception as e:
                        print(f"Error reading document barrel file {file_path}: {e}")  # Log the error for document barrel files

        if results:
            return json.dumps(results)  # Return the results as JSON
        else:
            return json.dumps({"error": "No results found."})

    except Exception as e:
        print(f"Unexpected error: {e}")
        return json.dumps({"error": f"An unexpected error occurred: {e}"})


# Entry point
if __name__ == "__main__":
    try:
        results = searchWord()
        print(results)  # Print results to stdout (this is what your server will capture)
    except Exception as e:
        print(json.dumps({"error": f"An unexpected error occurred: {e}"}))
