import os
import csv
import pandas as pd

def update_inverted_index(inverted_index_file, mdsample_file, lt_file):
    # Initialize the inverted index dictionary
    inverted_index = {}

    # Load the existing inverted index if the file exists and is not empty
    if os.path.exists(inverted_index_file) and os.path.getsize(inverted_index_file) > 0:
        print(f"Loading existing inverted index from {inverted_index_file}")
        try:
            # Open the file manually using the csv module for better control
            with open(inverted_index_file, 'r', newline='', encoding='ISO-8859-1') as file:
                reader = csv.reader(file)
                next(reader)  # Skip header row
                for row in reader:
                    token = row[0].strip()  # Token ID
                    doc_ids = row[1].strip()  # Document IDs
                    doc_ids_list = doc_ids.split(',,')
                    inverted_index[token] = set(doc_ids_list)  # Initialize as set to prevent duplicates
        except Exception as e:
            print(f"Error reading {inverted_index_file}: {e}")
            print("Proceeding with an empty inverted index.")
    else:
        print(f"No existing inverted index found or file is empty. Starting fresh.")

    # Load the CSV files for token data and combined token IDs
    fidx = pd.read_csv(mdsample_file)
    lidx = pd.read_csv(lt_file)

    # Extract token IDs from lt.csv
    token_ids = lidx['id'].astype(str).str.strip()

    # Iterate through each token ID and update the inverted index
    for token in token_ids:
        # For each row in the MergedData, check if token exists in the combined_token_ids
        for _, row in fidx.iterrows():
            doc_id = str(row['Id'])  # Get the document ID
            combined_token_ids = row['combined_token_ids']  # Get the combined token IDs

            # Split token IDs using commas and clean them
            tokens_in_row = {t.strip() for t in combined_token_ids.split(',')}  # Use set for unique tokens

            # If the token is in the current row's tokens, add it to the inverted index
            if token in tokens_in_row:
                if token not in inverted_index:
                    inverted_index[token] = set()  # Initialize as set for new token
                inverted_index[token].add(doc_id)  # Add document ID if not already present

    # Prepare to write the updated inverted index to the CSV file
    file_exists = os.path.exists(inverted_index_file)

    # If the file doesn't exist or is empty, write the header
    if not file_exists or os.path.getsize(inverted_index_file) == 0:
        with open(inverted_index_file, 'w', newline='', encoding='ISO-8859-1') as file:
            writer = csv.writer(file)
            writer.writerow(["Token_ID", "Document_IDs"])  # Write the header row

    # Append the updated inverted index to the file
    with open(inverted_index_file, 'a', newline='', encoding='ISO-8859-1') as file:
        writer = csv.writer(file)
        
        # Only append new tokens and their document IDs
        for token, doc_ids in inverted_index.items():
            doc_ids_str = ',,'.join(doc_ids)  # Join doc IDs with ',,'
            # Write the token and its document IDs to the file
            writer.writerow([token, doc_ids_str])

    print(f"Inverted index updated and saved to {inverted_index_file}")

    # Function to remove duplicates and save to the file
    def remove_duplicates_and_save(output_file_path):
        # Check if the output file exists
        if os.path.exists(output_file_path):
            # Read the existing data from the output CSV file
            output_data = pd.read_csv(output_file_path)
            
            # Remove duplicates based on all columns (including 'combined_token_ids')
            cleaned_data = output_data.drop_duplicates()

            # Write the cleaned data back to the output file
            cleaned_data.to_csv(output_file_path, index=False)
            print(f"Duplicates removed and cleaned data saved to {output_file_path}")

    # Call the function to remove duplicates and save the cleaned data
    remove_duplicates_and_save(inverted_index_file)

update_inverted_index("./dataset/InvertedIndex.csv", "./dataset/MergedData_with_tokens.csv", "./dataset/LemmatizedTags&Tokens.csv")
