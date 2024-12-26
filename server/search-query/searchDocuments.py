import sys
import os
import pandas as pd

# Add the '../lemmatizer' folder to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lemmatizer'))

# Now you can import the functions from lemmatizerfunctions
from lemmatizerfunctions import lemmatize_word, wordToken, remove_duplicates_and_save

def searchWord():
    try:
        # Get the word from the command line arguments
        if len(sys.argv) != 2:
            print("Usage: python script.py <word_to_search>")
            return []
        
        word = sys.argv[1]

        # Lemmatize the word
        lemmatized_word = lemmatize_word(word)

        # Tokenize the lemmatized word
        token = wordToken(lemmatized_word)

        # Check if the token is a valid value (for comparison with ranges)
        try:
            token_value = token  # Keep token as a string
        except ValueError:
            print("Token is not a valid value, skipping file range search.")
            return []

        # Retrieve documents from the ./Barrels folder where the token name is in the filename range
        barrel_folder = './dataset/barrels'
        found_files = []

        for file in os.listdir(barrel_folder):
            if '-' in file:
                start, end = file.split('-')
                try:
                    # Convert start and end to strings for comparison
                    start = str(start)
                    end = str(end)

                    # Check if the token falls within the range
                    if start is not None and start <= str(token_value) <= end:
                        found_files.append(file)
                except ValueError:
                    print(f"Invalid range format in filename: {file}")

        # Prepare the results to return
        results = []

        if found_files:
            for file in found_files:
                file_path = os.path.join(barrel_folder, file)
                
                # Ensure the file is not empty before attempting to read it
                if os.path.getsize(file_path) > 0:
                    try:
                        # Read the CSV file using pandas
                        df = pd.read_csv(file_path, encoding='ISO-8859-1')

                        # Create a dictionary for fast lookup: {Token_ID: Document_IDs}
                        token_dict = {}
                        for index, row in df.iterrows():
                            token_id = row['Token_ID']  # Use the Token_ID column
                            document_ids = row['Document_IDs']  # Use the Document_IDs column
                            
                            # Ensure the Document_IDs are stored as a comma-separated string
                            token_dict[token_id] = document_ids

                        # Search for both token_value and token_value# and append their results
                        document_found = None
                        document_found_hash = None

                        # Check for both token_value and token_value#
                        if str(token_value) in token_dict:
                            document_found = token_dict[str(token_value)]
                        if f"{token_value}#" in token_dict:
                            document_found_hash = token_dict[f"{token_value}#"]

                        # Combine both document results if both exist
                        if document_found or document_found_hash:
                            if document_found:
                                results.append([str(token_value), document_found])
                            if document_found_hash:
                                results.append([f"{token_value}#", document_found_hash])
                                                       
                    except Exception as e:
                        print(f"Error reading CSV file {file}: {e}")
                else:
                    print(f"File {file} is empty. Skipping.")
        else:
            print(f"No files found for token '{token}' within the range.")

        # Return the results instead of writing to a CSV
        if results:
            return results
        else:
            print("No results found.")
            return []

    except Exception as e:
        print(f"Error during processing: {e}")
        return []


output = searchWord()

