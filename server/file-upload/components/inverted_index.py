import pandas as pd
import os
import re

def inverted_index(combined_token_ids, document_id, barrel_folder):
    """
    Inserts the document ID into the corresponding inverted index barrel based on token IDs.
    Dynamically handles non-uniform barrel ranges and creates new barrels if needed.

    Args:
        combined_token_ids (str): Comma-separated token IDs (e.g., "1234#, 5678").
        document_id (int): The document ID to insert.
        barrel_folder (str): Path to the folder containing inverted index barrels.

    Returns:
        None
    """
    # Helper function to parse existing barrel ranges
    def get_existing_ranges():
        ranges = []
        if not os.path.exists(barrel_folder):
            os.makedirs(barrel_folder)
        for file_name in os.listdir(barrel_folder):
            match = re.match(r"(\d+)-(\d+)\.csv", file_name)
            if match:
                ranges.append((int(match.group(1)), int(match.group(2))))
        return sorted(ranges)

    # Helper function to generate new barrels until the token_id is covered
    def ensure_barrel_exists(token_id, ranges):
        if not ranges:
            return [(0, 3999)]  # Start with the first range if no barrels exist

        # Find the last range
        _, last_end = ranges[-1]

        while last_end < token_id:
            new_start = last_end + 1
            new_end = new_start + 3999
            ranges.append((new_start, new_end))
            last_end = new_end

        return ranges

    # Helper function to find the barrel for a token ID
    def find_barrel(token_id, ranges):
        for start, end in ranges:
            if start <= token_id <= end:
                return f"{start}-{end}.csv"
        return None

    # Split combined token IDs into individual tokens
    token_ids = [token.strip() for token in combined_token_ids[0].split(',') if token.strip()]

    # Get existing barrel ranges
    existing_ranges = get_existing_ranges()

    for token_id in token_ids:
        clean_token_id = token_id.strip()

        try:
            # Extract numeric part for determining barrel placement, handle '#' if present
            numeric_token_id = int(re.sub(r'[^0-9]', '', clean_token_id))

            # Ensure barrels exist to cover the token ID
            existing_ranges = ensure_barrel_exists(numeric_token_id, existing_ranges)

            # Find the barrel for the token ID
            barrel_name = find_barrel(numeric_token_id, existing_ranges)

            if barrel_name is None:
                print(f"Error: No barrel found for TokenID {clean_token_id}")
                continue  # Skip processing if no barrel is found

            barrel_file_path = os.path.join(barrel_folder, barrel_name)

            if os.path.exists(barrel_file_path):
                # If the barrel exists, read it into a DataFrame
                barrel_data = pd.read_csv(barrel_file_path, dtype={'Document_IDs': str, 'Token_ID': str})

                # Check if the token ID already exists in the barrel
                if 'Token_ID' not in barrel_data.columns:
                    print(f"Error: Column 'TokenID' not found in barrel {barrel_name}")
                    continue

                token_row = barrel_data.loc[barrel_data['Token_ID'] == clean_token_id]

                if not token_row.empty:
                    # Token exists, append the document ID if not already present
                    current_doc_ids = token_row.iloc[0]['Document_IDs']
                    doc_id_list = set(current_doc_ids.split(','))  # Split and use a set to avoid duplicates

                    # Add the document ID to the list if not already present
                    if str(document_id) not in doc_id_list:
                        doc_id_list.add(str(document_id))
                        updated_doc_ids = ','.join(sorted(doc_id_list))  # Ensure sorted order
                        barrel_data.loc[barrel_data['Token_ID'] == clean_token_id, 'Document_IDs'] = updated_doc_ids
                        barrel_data.to_csv(barrel_file_path, index=False)  # Save the updated barrel
                        print(f"Updated barrel {barrel_name} for TokenID {clean_token_id}")
                else:
                    # Token does not exist, add a new row
                    new_row = {
                        'Token_ID': clean_token_id,
                        'Document_IDs': str(document_id)
                    }
                    barrel_data = pd.concat([barrel_data, pd.DataFrame([new_row])], ignore_index=True)
                    barrel_data.to_csv(barrel_file_path, index=False)
                    print(f"Inserted new TokenID {clean_token_id} in barrel {barrel_name}")
            else:
                # Barrel does not exist, create a new one
                new_row = {
                    'Token_ID': clean_token_id,
                    'Document_IDs': str(document_id)
                }
                new_df = pd.DataFrame([new_row])
                new_df.to_csv(barrel_file_path, index=False)
                print(f"Created new barrel {barrel_name} with TokenID {clean_token_id}")

        except Exception as e:
            print(f"Error processing TokenID {clean_token_id}: {e}")
