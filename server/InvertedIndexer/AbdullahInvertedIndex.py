import pandas as pd
import os

def create_inverted_index(input_file_path, output_file_path):
    # Check if the input file exists
    if not os.path.exists(input_file_path):
        print(f"Input file {input_file_path} does not exist.")
        return

    # Read the forward index data
    data = pd.read_csv(input_file_path)

    # Initialize a dictionary to store the inverted index
    inverted_index = {}

    # Iterate through each row in the dataset
    for index, row in data.iterrows():
        # Extract the combined token IDs
        token_ids = str(row['combined_token_ids']).split(', ')
        
        # Map each token ID to the current row index (or another identifier, e.g., row['Id'])
        for token_id in token_ids:
            token_id = token_id.strip()  # Clean the token ID
            if token_id:  # Skip empty tokens
                if token_id not in inverted_index:
                    inverted_index[token_id] = []  # Initialize a list for this token ID
                inverted_index[token_id].append(index)  # Append the row index to the list

    # Convert the inverted index dictionary into a DataFrame for saving
    inverted_index_df = pd.DataFrame([
        {'token_id': token_id, 'row_indices': ', '.join(map(str, rows))}
        for token_id, rows in inverted_index.items()
    ])

    # Save the inverted index to the output file
    inverted_index_df.to_csv(output_file_path, index=False)
    print(f"Inverted index saved to {output_file_path}")

# Example usage
create_inverted_index("./dataset/MergedData_with_tokens.csv", "./dataset/inverted_indexa.csv")
