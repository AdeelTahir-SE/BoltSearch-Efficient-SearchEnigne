import os
import json
import csv
import sys

def convert_json_to_csv(json_file_path):
    try:
        # Check if the file exists
        if not os.path.exists(json_file_path):
            print(f"File not found: {json_file_path}")
            return

        # Open the JSON file and load its content
        with open(json_file_path, 'r') as f:
            data = json.load(f)

        # Define the CSV file path
        csv_file_path = json_file_path.replace('.json', '.csv')




        # Open a CSV file for writing
        with open(csv_file_path, 'w', newline='') as csvfile:
            if data:
                writer = csv.DictWriter(csvfile, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
                print(f"Conversion successful: {json_file_path} -> {csv_file_path}")
            else:
                print(f"JSON file is empty: {json_file_path}")

    
        os.remove(json_file_path)
        print(f"Deleted original JSON file: {json_file_path}")
    except Exception as e:
        print(f"Error during conversion: {e}")

# Get the file path from the command line arguments
if len(sys.argv) != 2:
    print(sys.argv[0])
else:
    json_file_path = sys.argv[1]
    convert_json_to_csv(json_file_path)
