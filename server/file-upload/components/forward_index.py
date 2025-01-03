import pandas as pd
import re
import sys
import os
import json

# Add the 'server/lemmatizer' directory to the sys.path for module import
lemmatizer_dir = os.path.join(os.getcwd(), 'lemmatizer')  # Construct the path
if lemmatizer_dir not in sys.path:  # Add the directory to sys.path only if it's not already there
    sys.path.append(lemmatizer_dir)

# Now import the lemmatizer functions
from lemmatizerfunctions import lemmatize_word

# Function to check if a document with the given ID already exists in the specific barrel file
def is_document_exists_in_barrel(barrel_file_path, doc_id):
    """Check if the document ID already exists in the specific barrel file."""
    if os.path.exists(barrel_file_path):
        try:
            barrel_data = pd.read_csv(barrel_file_path)
            existing_ids = set(barrel_data['Id'].values)  # Convert to set for faster lookup
            if doc_id in existing_ids:
                return True  # Document ID exists in this barrel file
        except Exception as e:
            print(f"Error reading {barrel_file_path}: {e}")
    return False

# Function to process and append new document to forward index barrel
def process_and_append_to_barrel(input_file_path, barrel_folder):
    # Read the JSON dataset
    with open(input_file_path, 'r', encoding='ISO-8859-1') as f:
        data = json.load(f)

    # Helper function to lemmatize and split text
    def process_text(text):
        if not isinstance(text, str):  # Handle NaN or None values
            return []
        # Use a more comprehensive regular expression for tokenizing words
        tokens = re.findall(r'\b\w+\b', text.lower())  # Tokenize by word boundaries
        return [lemmatize_word(token) for token in tokens]

    # Function to generate a token ID by summing ASCII values of the characters in the word
    def wordToken(text):
        text = text.lower()  # Normalize to lowercase for case insensitivity
        unique_sum = 0  # Initialize a sum to calculate uniqueness
        prime = 31  # Prime number to reduce collisions

        for index, char in enumerate(text, start=1):
            unique_sum += ord(char) * index * prime  # Combine ASCII, position, and prime

        # Add the length of the string and its ASCII sum for further uniqueness
        unique_sum *= len(text)
        ascii_sum = sum(ord(c) for c in text)
        unique_sum += ascii_sum

        # Ensure it’s a large and unique output
        return abs(unique_sum)

    # Helper function to process token IDs for title or tag
    def process_token_ids(tokens, is_title=False):
        token_ids = []
        seen_tokens = set()  # Set to keep track of already processed tokens
        for token in tokens:
            token = token.strip()
            if token and token not in seen_tokens:  # Only process unique words
                token_id = wordToken(token)  # Generate token ID using wordToken function
                if is_title:
                    # Append "#" for tokens from the Title
                    token_ids.append(f"{token_id}#")
                else:
                    # Keep the token ID as is for the Tags
                    token_ids.append(str(token_id))  # Convert to string for consistency
                seen_tokens.add(token)  # Mark this token as processed
        return ', '.join(token_ids)

    # Initialize a list to store processed data and token IDs
    processed_data = []
    combined_token_ids_list = []
    
    # Process each document in the JSON data
    for doc in data:
        doc_id = doc.get('id')

        # Determine the barrel name and path based on document ID
        barrel_name = f"barrel_{(doc_id // 4000) * 4000}_to_{(doc_id // 4000) * 4000 + 3999}.csv"
        barrel_file_path = os.path.join(barrel_folder, barrel_name)

        if is_document_exists_in_barrel(barrel_file_path, doc_id):
            print(f"Document with ID {doc_id} already exists in barrel {barrel_name}. Skipping append.")
            continue  # Skip the document if it already exists in this barrel

        # Process Title tokens
        title_tokens = process_text(doc.get('Title', ''))  # Lemmatize the Title tokens
        title_token_ids = process_token_ids(title_tokens, is_title=True)

        # Process Tag tokens
        tag_tokens = process_text(doc.get('Tag', ''))  # Lemmatize the Tag tokens
        tag_token_ids = process_token_ids(tag_tokens, is_title=False)

        # Combine title and tag token IDs into one column
        combined_token_ids = f"{title_token_ids}, {tag_token_ids}" if title_token_ids or tag_token_ids else ''
        combined_token_ids_list.append(combined_token_ids)

        # Add the combined token IDs to the document
        doc['combined_token_ids'] = combined_token_ids
        processed_data.append(doc)

    # Convert the processed data into a DataFrame
    processed_df = pd.DataFrame(processed_data)

    if processed_data:
        # Append or create the barrel file
        if os.path.exists(barrel_file_path):
            processed_df.to_csv(barrel_file_path, mode='a', header=False, index=False)
            print(f"Document appended to existing barrel: {barrel_file_path}")
        else:
            processed_df.to_csv(barrel_file_path, index=False)
            print(f"New barrel created: {barrel_file_path}")

    # Return the name of the newly added barrel and combined token IDs
    # Delete the input JSON file after processing
    try:
        os.remove(input_file_path)
        print(f"Deleted the JSON file: {input_file_path}")
    except Exception as e:
        print(f"Error deleting the JSON file: {e}")

    print(combined_token_ids_list)
    return [combined_token_ids_list, doc_id]

# Main function to execute the process
def main():
    if len(sys.argv) != 2:
        print("Usage: python process_json.py <input_json_file_path>")
        sys.exit(1)
    
    input_file_path = sys.argv[1]
    forward_index_barrel_folder = os.path.join(os.getcwd(), "dataset", "DocumentBarrels")
    inverted_index_barrel_folder = os.path.join(os.getcwd(), "dataset", "barrels")

    if not os.path.exists(input_file_path):
        print(f"Error: The file {input_file_path} does not exist.")
        sys.exit(1)

    if not os.path.exists(forward_index_barrel_folder):
        print(f"Error: The forward index barrel folder {forward_index_barrel_folder} does not exist.")
        sys.exit(1)

    if not os.path.exists(inverted_index_barrel_folder):
        print(f"Error: The inverted index barrel folder {inverted_index_barrel_folder} does not exist.")
        sys.exit(1)

    try:
        print(f"Processing file {input_file_path} and appending to forward index barrels in {forward_index_barrel_folder}...")
        combined_token_ids_list = process_and_append_to_barrel(input_file_path, forward_index_barrel_folder)
        print("Received combined_token_ids_list:", combined_token_ids_list)
        
        if combined_token_ids_list and len(combined_token_ids_list) == 2:
            # Assuming you have an inverted_index function to handle the second part of processing
            inverted_index(combined_token_ids_list[0], combined_token_ids_list[1], inverted_index_barrel_folder)
        else:
            print(f"Error: Invalid token list returned: {combined_token_ids_list}")
            sys.exit(1)

        print("Processing completed successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

