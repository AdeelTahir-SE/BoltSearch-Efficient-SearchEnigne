import pandas as pd
import os

def create_Inverted_Index(input_file, output_file):
    try:
        # Check if the input file exists
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"Input file '{input_file}' does not exist.")

        # Read the input file into a DataFrame
        df = pd.read_csv(input_file)

        # Check if required columns exist
        required_columns = ['combined_token_ids', 'Id']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Input file is missing required columns: {', '.join(missing_columns)}")

        # Check if DataFrame is empty
        if df.empty:
            raise ValueError("Input file is empty.")

        # Create a dictionary to store the inverted index
        inverted_index = {}

        # Build the inverted index
        for _, row in df.iterrows():
            token_ids = str(row['combined_token_ids']).split()
            for word in token_ids:
                # Remove any commas from the token_id (if any)
                clean_word = word.replace(",", "")
                # Add the ID to the set for the word
                inverted_index.setdefault(clean_word, set()).add(row['Id'])

        # Prepare data for output
        output_data = []
        for word, ids in inverted_index.items():
            # Convert the set of IDs to a comma-separated string
            output_data.append({'Token_ID': word, 'Document_IDs': ",".join(map(str, sorted(ids)))})

        # Write the inverted index to the output CSV file
        output_df = pd.DataFrame(output_data)
        output_df.to_csv(output_file, index=False)

        print(f"Inverted index created successfully: {output_file}")
        return output_file

    except FileNotFoundError as fnf_error:
        print(f"Error: {fnf_error}")
    except pd.errors.EmptyDataError:
        print("Error: Input file is empty or only contains headers.")
    except pd.errors.ParserError:
        print("Error: Failed to parse input file. Check file formatting.")
    except ValueError as ve:
        print(f"Error: {ve}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

# Example usage
create_Inverted_Index("./dataset/MergedData_with_tokens.csv", "./dataset/Inverted_Index.csv")
