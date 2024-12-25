import os
import csv
from collections import defaultdict

def create_barrels_with_range(inverted_index_file, barrel_dir, num_barrels=500):
    if not os.path.exists(inverted_index_file):
        print(f"File {inverted_index_file} does not exist.")
        return

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

    # If there are fewer tokens than barrels, adjust the number of barrels to the number of tokens
    total_tokens = len(sorted_tokens)
    num_barrels = min(num_barrels, total_tokens)  # Adjust the number of barrels if needed

    # Calculate how many tokens should go into each barrel
    tokens_per_barrel = total_tokens // num_barrels
    remainder = total_tokens % num_barrels  # Handle any remaining tokens

    # Iterate over the tokens to assign them to barrels
    current_barrel = defaultdict(list)
    barrel_start = None
    barrel_end = None
    token_index = 0

    for barrel_num in range(num_barrels):
        # Calculate the range of tokens for the current barrel
        if barrel_num < remainder:
            barrel_size = tokens_per_barrel + 1  # Extra token for this barrel
        else:
            barrel_size = tokens_per_barrel

        barrel_tokens = sorted_tokens[token_index:token_index + barrel_size]
        token_index += barrel_size

        # Set barrel start and end tokens
        barrel_start = barrel_tokens[0]
        barrel_end = barrel_tokens[-1]

        # Fill the current barrel with the document IDs of these tokens
        current_barrel = {token: inverted_index[token] for token in barrel_tokens}

        # Create or update the barrel file
        barrel_filename = f"{barrel_start}-{barrel_end}.csv"
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
    inverted_index_file="./dataset/invertedindexsample.csv",  # New inverted index file
    barrel_dir="./dataset/barrels",  # Path to your barrel directory
    num_barrels=5  # Default is 500 barrels, but it will be adjusted if tokens are fewer than 500
)