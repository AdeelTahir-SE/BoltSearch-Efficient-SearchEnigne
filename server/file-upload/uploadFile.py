import sys
import os
import json

functions = os.path.join(os.getcwd(), "file-upload", 'components')  # Construct the path
print(functions)
if functions not in sys.path:  # Add the directory to sys.path only if it's not already there
    sys.path.append(functions)

from forward_index import process_and_append_to_barrel 
from inverted_index import inverted_index 

def main():
    if len(sys.argv) != 2:
        print("Usage: python process_json.py <input_json_file_path>")
        sys.exit(1)
    print(sys.argv[1])
    input_file_path = sys.argv[1]
    forward_index_barrel_folder = os.path.join(os.getcwd(),"dataset","DocumentBarrels")
    inverted_index_barrel_folder = os.path.join(os.getcwd(),"dataset","barrels")

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
            inverted_index(combined_token_ids_list[0], combined_token_ids_list[1], inverted_index_barrel_folder)
        else:
            print(f"Error: Invalid token list returned: {combined_token_ids_list}")
            sys.exit(1)

        print("Processing completed successfully.")

    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

main()
