import pandas as pds

# Load the CSV files
lidx = pds.read_csv("./jsondataset/LemmatizedTags&Tokens.csv")
fidx = pds.read_csv("./jsondataset/MergedData_with_tokens.csv")

# Initialize the inverted index dictionary
inverted_index = {}

# Extract token IDs from lt.csv
token_ids = lidx['id']

# Iterate through each token ID and build the inverted index
for token in token_ids:
    token = str(token).strip()  # Ensure token is a string and clean
    for index, row in fidx.iterrows():
        doc_id = str(row['Id'])  # Get the document ID
        combined_token_ids = row['combined_token_ids']  # Get the combined token IDs

        # Split token IDs using commas and clean them
        tokens_in_row = [t.strip() for t in combined_token_ids.split(',')]

        # Check if the token is in the current row's tokens
        if token in tokens_in_row:
            if token not in inverted_index:
                inverted_index[token] = []  # Initialize list for new token
            inverted_index[token].append(doc_id)  # Add document ID to the list

# Save the inverted index to a CSV file
output_file = "./jsondataset/InvertedIndex.csv"
with open(output_file, 'w') as file:
    # Write the header
    file.write("Token ID,Document IDs\n")
    # Write each token and its associated document IDs
    for token, doc_ids in inverted_index.items():
        file.write(f"{token},{','.join(doc_ids)}\n")

print(f"Inverted index saved to {output_file}")
