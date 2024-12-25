import sys
import os
import csv

# Add the '../lemmatizer' folder to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lemmatizer'))

# Now you can import the functions from lemmatizerfunctions
from lemmatizerfunctions import lemmatize_word, wordToken, remove_duplicates_and_save

def searchWord():
    try:
        # Get the word from the command line arguments
        if len(sys.argv) != 2:
            print("Usage: python script.py <word_to_search>")
            return
        
        word = sys.argv[1]

        # Lemmatize the word
        lemmatized_word = lemmatize_word(word)
        print(f"Lemmatized word: {lemmatized_word}")

        # Tokenize the lemmatized word
        token = wordToken(lemmatized_word)
        print(f"Tokenized word: {token}")

        # Check if the token is a numeric value (for comparison with ranges)
        try:
            token_value = int(token)  # Convert token to an integer for comparison
        except ValueError:
            print("Token is not a numeric value, skipping file range search.")
            return

        # Retrieve documents from the ./Barrels folder where the token name is in the filename range
        barrel_folder = '../dataset/barrels'
        found_files = []

        for file in os.listdir(barrel_folder):
            # Assuming the filenames are in the format 'start-end' (e.g., '123-451')
            if '-' in file:
                start, end = file.split('-')
                try:
                    # Convert start and end to integers for comparison
                    start = (start)
                    end = (end)
                    
                    # Check if the token falls within the range (comparison done with integers)
                    if start <= str(token_value) <= end:
                        found_files.append(file)
                except ValueError:
                    print(f"Invalid range format in filename: {file}")

        if found_files:
            print(f"Found documents for token '{token}':")
            for file in found_files:
                file_path = os.path.join(barrel_folder, file)
                
                # Ensure the file is not empty before attempting to read it
                if os.path.getsize(file_path) > 0:
                    try:
                        # Read CSV content from the file
                        with open(file_path, 'r', encoding='ISO-8859-1') as f:
                            reader = csv.reader(f)
                            headers = next(reader)  # Skip the header
                            
                            # Search for the document with the matching ID (which is the token value)
                            document_found = None
                            for row in reader:
                                try:
                                    # Assuming the first column contains the document ID
                                    doc_id = int(row[0])  # Adjust index if the document ID is elsewhere
                                    if doc_id == token_value:
                                        document_found = row
                                        break
                                except ValueError:
                                    continue
                            
                            # Print the document if found
                            if document_found:
                                print(f"Document found in file {file}: {document_found}")
                            else:
                                print(f"No document found with ID {token_value} in file {file}")
                    except Exception as e:
                        print(f"Error reading CSV file {file}: {e}")
                else:
                    print(f"File {file} is empty. Skipping.")
        else:
            print(f"No files found for token '{token}' within the range.")

    except Exception as e:
        print(f"Error during processing: {e}")

# Run the search function
searchWord()
