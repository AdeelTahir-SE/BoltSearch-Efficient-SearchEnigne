import pyarrow.parquet as pq
import pandas as pd
import traceback

# File path for the Parquet file
input_file_path = "./server/jsondataset/FinalMergedData.parquet"  # Update with the correct file path
output_file_path = "./server/jsondataset/filtered_row_output.txt"  # File to write the output

def get_row_by_id(file_path, target_id, output_file):
    try:
        # Read the Parquet file
        table = pq.read_table(file_path)
        df = table.to_pandas()

        # Print column names for debugging
        output_file.write(f"Columns in the DataFrame: {df.columns}\n")

        # Check if 'Id' or 'id' exists and filter
        column_name = 'Id' if 'Id' in df.columns else ('id' if 'id' in df.columns else None)
        
        if column_name is None:
            output_file.write("Error: 'Id' or 'id' column not found in the DataFrame.\n")
            return

        # Filter the DataFrame to get the row with the specific 'Id'
        filtered_row = df[df[column_name] == target_id]

        # Check if the row exists and return it
        if not filtered_row.empty:
            output_file.write(f"Row with Id {target_id} found:\n")
            output_file.write(filtered_row.to_string(index=False))  # Write the row without index
        else:
            output_file.write(f"No row found with Id {target_id}\n")

    except Exception as e:
        output_file.write(f"Error processing Parquet file: {str(e)}\n")
        traceback.print_exc()

# Specify the Id to search for
target_id = 180

# Open the output file for writing
with open(output_file_path, 'w') as output_file:
    get_row_by_id(input_file_path, target_id, output_file)

print(f"Result written to {output_file_path}")
