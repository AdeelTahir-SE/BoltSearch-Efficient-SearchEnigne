import pyarrow.parquet as pq
import pyarrow as pa
import pandas as pd
import traceback
import sys

# File paths for Parquet files
merged_data_file_path = "./server/jsondataset/MergedData.parquet"
answers_file_path = "./server/jsondataset/Answers.parquet"
output_file_path = "./server/jsondataset/FinalMergedData.parquet"

def process_parquet_file(file_path):
    try:
        table = pq.read_table(file_path)
        return table.to_pandas()
    except Exception as e:
        print(f"Error reading Parquet file {file_path}: {str(e)}")
        traceback.print_exc()
        return pd.DataFrame()

def merge_with_answers():
    try:
        print("Processing started...")

        # Load MergedData (Questions + Tags)
        merged_data = process_parquet_file(merged_data_file_path)
        print(f"Loaded MergedData with {len(merged_data)} rows")
        print("MergedData columns:", merged_data.columns)

        # Rename question-related columns
        merged_data.rename(columns={
            'Body': 'Body_Question',
            'CreationDate': 'CreationDate_Question',
            'Score': 'Score_Question'
        }, inplace=True)

        # Load Answers
        answers_df = process_parquet_file(answers_file_path)
        print(f"Loaded Answers with {len(answers_df)} rows")
        print("Answers columns:", answers_df.columns)

        # Check if necessary columns exist
        if 'Id' not in merged_data.columns:
            print("Error: 'Id' column not found in MergedData.")
            return
        if 'ParentId' not in answers_df.columns:
            print("Error: 'ParentId' column not found in Answers.")
            return

        # Select specific columns from Answers
        answers_df = answers_df[['ParentId', 'Body', 'CreationDate', 'Score']]
        answers_df.rename(columns={
            'Body': 'Body_Answer',
            'CreationDate': 'CreationDate_Answer',
            'Score': 'Score_Answer'
        }, inplace=True)

        # Merge MergedData with Answers
        print("Merging MergedData with Answers...")
        final_merged_data = merged_data.merge(
            answers_df,
            left_on="Id",      # Match Questions' Id with Answers' ParentId
            right_on="ParentId",
            how="left"         # Include all rows from MergedData
        )

        # Drop the redundant 'ParentId' column
        final_merged_data.drop(columns=['ParentId'], inplace=True)

        print(f"Final merged data has {len(final_merged_data)} rows.")
        print("Final merged data columns:", final_merged_data.columns)

        # Write the final merged data to a Parquet file
        merged_table = pa.Table.from_pandas(final_merged_data)
        pq.write_table(merged_table, output_file_path)

        print(f"Final merged data successfully written to {output_file_path}")

    except Exception as e:
        print(f"Error merging data: {str(e)}")
        traceback.print_exc()
        sys.exit(1)

# Run the script
merge_with_answers()
