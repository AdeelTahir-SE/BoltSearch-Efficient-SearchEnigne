import os
import csv
from collections import defaultdict

def create_barrels_with_range(inverted_index_file, barrel_dir, tokens_per_barrel=3000):
    if not os.path.exists(inverted_index_file):
        print(f"File {inverted_index_file} does not exist.")
        return

    # Increase CSV field size limit to a high but manageable value
    csv.field_size_limit(10**9)

    # Ensure the barrel directory exists
    os.makedirs(barrel_dir, exist_ok=True)

    # Read the inverted index file and store data
    inverted_index = defaultdict(set)
    with open(inverted_index_file, 'r', encoding='ISO-8859-1') as file:
        reader = csv.reader(file)
        next(reader)  # Skip header
        for row in reader:
            token = row[0].strip()
            doc_ids = row[1].strip().split(',,')
            
            # Process the token to separate the # if present
            if '#' in token:
                base_token, hash_part = token.split('#', 1)
                token = base_token + '#' + hash_part  # Keep the full token for the barrel
            inverted_index[token].update(doc_ids)

    # Sort tokens by Token_ID (numerically if possible)
    sorted_tokens = sorted(inverted_index.keys(), key=lambda x: int(x.split('#')[0]))

    # Calculate the number of barrels needed based on the tokens_per_barrel
    total_tokens = len(sorted_tokens)
    num_barrels = (total_tokens + tokens_per_barrel - 1) // tokens_per_barrel  # Ceiling division

    # Iterate over the tokens to assign them to barrels
    token_index = 0

    for barrel_num in range(num_barrels):
        # Calculate the range of tokens for the current barrel
        barrel_tokens = sorted_tokens[token_index:token_index + tokens_per_barrel]
        token_index += len(barrel_tokens)

        # Set barrel start and end tokens
        barrel_start = barrel_tokens[0]
        barrel_end = barrel_tokens[-1]

        # Fill the current barrel with the document IDs of these tokens
        current_barrel = {token: inverted_index[token] for token in barrel_tokens}

        # Create or update the barrel file
        barrel_filename = f"{barrel_start.split('#')[0]}-{barrel_end.split('#')[0]}.csv"
        barrel_file_path = os.path.join(barrel_dir, barrel_filename)

        # Write the barrel data to the file
        with open(barrel_file_path, 'w', newline='', encoding='ISO-8859-1') as barrel_file:
            writer = csv.writer(barrel_file)
            writer.writerow(["Token_ID", "Document_IDs"])

            # Write the tokens and their document IDs
            for token, doc_ids in sorted(current_barrel.items(), key=lambda x: int(x[0].split('#')[0])):
                writer.writerow([token, ',,'.join(doc_ids)])

        print(f"Barrel {barrel_start}-{barrel_end} created with {len(current_barrel)} tokens.")

# Example usage
create_barrels_with_range(
    inverted_index_file="./dataset/inverted_indexa.csv",  # New inverted index file
    barrel_dir="./dataset/barrels",  # Path to your barrel directory
    tokens_per_barrel=3000  # Specify 3000 tokens per barrel
)
