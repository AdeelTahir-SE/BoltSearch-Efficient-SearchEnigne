import pyarrow.parquet as pq
import pyarrow as pa
import pandas as pd
import traceback
import sys

# File paths for Parquet files
questions_file_path = "./server/jsondataset/Questions.parquet"
tags_file_path = "./server/jsondataset/Tags.parquet"
output_file_path = "./server/jsondataset/MergedData.parquet"

def process_parquet_file_by_row_groups(file_path, filter_fn):
    # Read the Parquet file
    reader = pq.ParquetFile(file_path)

    def process_row_group(i):
        row_group_table = reader.read_row_group(i)  # Read a single row group
        df = row_group_table.to_pandas()
        return df[filter_fn(df)]  # Apply filter on DataFrame in bulk

    try:
        # Process each row group and concatenate results
        results = [process_row_group(i) for i in range(reader.num_row_groups)]
        return pd.concat(results, ignore_index=True)
    except Exception as e:
        print(f"Error during Parquet file processing for {file_path}: {str(e)}")
        traceback.print_exc()
        return pd.DataFrame()  # Return an empty DataFrame on error

def process_data_with_parquet_chunks():
    try:
        print("Processing started...")

        # Read and process Questions
        questions_df = process_parquet_file_by_row_groups(
            questions_file_path,
            lambda q: q["Id"] % 10 == 0  # Filter for questions whose Id is a multiple of 10
        )
        print(f"Filtered Questions: {len(questions_df)}")
        print("Questions columns:", questions_df.columns)

        # Check for missing 'Id' in Questions
        if 'Id' not in questions_df.columns:
            print("Error: 'Id' column not found in Questions DataFrame.")
            print(f"Actual columns in Questions DataFrame: {questions_df.columns}")
            return

        # Read and process Tags (no specific filter, return all rows)
        tags_df = process_parquet_file_by_row_groups(
            tags_file_path,
            lambda t: pd.Series([True] * len(t))  # Return all rows for Tags
        )
        print(f"Filtered Tags: {len(tags_df)}")
        print("Tags columns:", tags_df.columns)

        # Check if the necessary 'Id' column exists in the Tags DataFrame
        if 'Id' not in tags_df.columns:
            print("Error: 'Id' column not found in Tags DataFrame.")
            print(f"Actual columns in Tags DataFrame: {tags_df.columns}")
            return

        # Merging Questions and Tags
        print("Merging Questions and Tags...")
        merged_data = questions_df.merge(
            tags_df,
            left_on="Id",
            right_on="Id",
            how="left"
        )

        # Group by 'Id' and aggregate tags into a comma-separated string
        print("Aggregating tags into a comma-separated string...")
        merged_data_grouped = merged_data.groupby('Id').agg({
            'Tag': lambda x: ', '.join(x.unique())  # Aggregate unique tags into a comma-separated string
        }).reset_index()

        # Merge the aggregated tags back into the original DataFrame
        final_merged_data = pd.merge(
            questions_df[['Id', 'Title', 'Body', 'CreationDate', 'Score']],
            merged_data_grouped,
            on='Id',
            how='left'
        )

        # Rename the 'Tag' column to 'Tags' for clarity
        final_merged_data.rename(columns={'Tag': 'Tags'}, inplace=True)

        # Write the final merged data to a Parquet file
        merged_table = pa.Table.from_pandas(final_merged_data)
        pq.write_table(merged_table, output_file_path)

        print(f"Merged data (Questions + Tags) successfully written to {output_file_path}")

    except Exception as e:
        print(f"Error processing Parquet data: {str(e)}")
        traceback.print_exc()
        sys.exit(1)

# Run the script
process_data_with_parquet_chunks()
