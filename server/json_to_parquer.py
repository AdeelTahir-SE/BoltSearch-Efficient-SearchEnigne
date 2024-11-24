import pyarrow.parquet as pq
import pyarrow as pa
import pandas as pd
import traceback
import sys

# File paths for Parquet files
questions_file_path = "./server/jsondataset/Questions.parquet"
answers_file_path = "./server/jsondataset/Answers.parquet"
tags_file_path = "./server/jsondataset/Tags.parquet"
output_file_path = "./server/jsondataset/MergedData.parquet"

def process_parquet_file_by_row_groups(file_path, filter_fn):
    # Read the Parquet file
    reader = pq.ParquetFile(file_path)
    filtered_records = []

    def process_row_group(i):
        row_group_table = reader.read_row_group(i)  # Read a single row group
        df = row_group_table.to_pandas()
        filtered_df = df[filter_fn(df)]  # Apply filter on DataFrame in bulk
        return filtered_df

    try:
        # Process each row group in parallel or sequentially
        results = []
        for i in range(reader.num_row_groups):
            results.append(process_row_group(i))
        filtered_records = pd.concat(results, ignore_index=True)
        return filtered_records
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

        # Read and process Answers
        answers_df = process_parquet_file_by_row_groups(
            answers_file_path,
            lambda a: a["ParentId"].isin(questions_df["Id"])  # Filter answers related to the questions
        )
        print(f"Filtered Answers: {len(answers_df)}")
        print("Answers columns:", answers_df.columns)

        # Check for missing 'ParentId' in Answers
        if 'ParentId' not in answers_df.columns:
            print("Error: 'ParentId' column not found in Answers DataFrame.")
            print(f"Actual columns in Answers DataFrame: {answers_df.columns}")
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

        # Merge data efficiently using pandas merge
        print("Merging Questions and Answers...")
        merged_data = questions_df.merge(
            answers_df,
            left_on="Id",
            right_on="ParentId",
            how="left"
        )

        print("Merging with Tags...")
        merged_data = merged_data.merge(
            tags_df,
            left_on="Id",
            right_on="Id",
            how="left"
        )

        # Group by question and aggregate answers and tags
        merged_data_grouped = merged_data.groupby("Id").agg({
            "Title": "first",  # Adjust based on the column names in your dataset
            "Body": "first",
            "answers": lambda x: x.tolist(),
            "tags": lambda x: x.tolist()
        }).reset_index()

        # Write merged data to a Parquet file
        merged_table = pa.Table.from_pandas(merged_data_grouped)
        pq.write_table(merged_table, output_file_path)

        print(f"Merged data successfully written to {output_file_path}")

    except Exception as e:
        print(f"Error processing Parquet data: {str(e)}")
        traceback.print_exc()
        sys.exit(1)

# Run the script
process_data_with_parquet_chunks()
