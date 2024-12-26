import sys
import os
import pandas as pd
from collections import defaultdict
import json

# Add the '../lemmatizer' folder to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lemmatizer'))

# Import custom lemmatizer functions
from lemmatizerfunctions import lemmatize_word, wordToken

def searchWord():
    try:
        # Validate command-line arguments
        if len(sys.argv) != 2:
            print("Usage: python script.py <word_to_search>")
            return []

        word = sys.argv[1]

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
        for file in found_token_files:
            file_path = os.path.join(token_barrel_folder, file)

            if os.path.isfile(file_path) and os.path.getsize(file_path) > 0:
                try:
                    # Read the CSV file without specifying encoding
                    df = pd.read_csv(file_path)

                    # Create a dictionary for token lookups
                    token_dict = defaultdict(str)
                    for _, row in df.iterrows():
                        token_dict[str(row['Token_ID'])] = row['Document_IDs']

                    # Search for token and token#
                    if token in token_dict:
                        document_ids.extend(token_dict[token].split(','))
                    if f"{token}#" in token_dict:
                        document_ids.extend(token_dict[f"{token}#"].split(','))
                except Exception as e:
                    pass  # Skip files that couldn't be read

        # Step 4: Search for documents in corresponding document barrels
        document_barrel_folder = './dataset/DocumentBarrels'
        if not os.path.isdir(document_barrel_folder):
            return json.dumps({"error": f"Document barrel folder '{document_barrel_folder}' does not exist."})

        results = []
        if document_ids:
            for doc_id in document_ids:
                barrel_file = f"barrel_{(int(doc_id) // 4000) * 4000}_to_{(int(doc_id) // 4000) * 4000 + 3999}.csv"
                file_path = os.path.join(document_barrel_folder, barrel_file)

                if os.path.isfile(file_path) and os.path.getsize(file_path) > 0:
                    try:
                        # Read the document barrel file without specifying encoding
                        df = pd.read_csv(file_path)

                        # Filter for the document ID
                        matching_docs = df[df['Id'] == int(doc_id)]
                        if not matching_docs.empty:
                            # Clean the data to remove NaN values
                            cleaned_docs = matching_docs.where(pd.notnull(matching_docs), None)
                            results.extend(cleaned_docs.to_dict(orient='records'))
                    except Exception as e:
                        pass  # Skip files that couldn't be read

        # Return results as JSON
        return json.dumps(results)

    except Exception as e:
        return json.dumps({"error": str(e)})

# Entry point
if __name__ == "__main__":
    try:
        results = searchWord()
        print(results)  # Print results to stdout (this is what your server will capture)
    except Exception as e:
        print(json.dumps({"error": f"An unexpected error occurred: {e}"}))
