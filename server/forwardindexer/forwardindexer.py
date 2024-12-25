import pandas as pd
import re
import sys
import os

# Add the 'server/lemmatizer' directory to the sys.path for module import
lemmatizer_dir = os.path.join(os.getcwd(), 'lemmatizer')  # Construct the path
if lemmatizer_dir not in sys.path:  # Add the directory to sys.path only if it's not already there
    sys.path.append(lemmatizer_dir)

# Now import the lemmatizer functions
from lemmatizerfunctions import lemmatize_word, wordToken


def process_data(input_file_path, output_file_path):
    # Read the dataset
    data = pd.read_csv(input_file_path, encoding='ISO-8859-1')

    # Helper function to lemmatize and split text
    def process_text(text):
        if not isinstance(text, str):  # Handle NaN or None values
            return []
        tokens = re.split(r'[ ,]', text)
        return [lemmatize_word(token.strip()) for token in tokens if token.strip()]

    # Function to generate a token ID by summing ASCII values of the characters in the word
    def wordToken(text):
        text = text.lower()  # Normalize to lowercase for case insensitivity
        unique_sum = 0  # Initialize a sum to calculate uniqueness
        prime = 31  # Prime number to reduce collisions

        for index, char in enumerate(text, start=1):
            unique_sum += ord(char) * index * prime  # Combine ASCII, position, and prime

        # Add the length of the string and its ASCII sum for further uniqueness
        unique_sum *= len(text)
        ascii_sum = sum(ord(c) for c in text)
        unique_sum += ascii_sum

        # Ensure it’s a large and unique output
        return abs(unique_sum)

    # Helper function to process token IDs for title or tag
    def process_token_ids(tokens, is_title=False):
        token_ids = []
        seen_tokens = set()  # Set to keep track of already processed tokens
        for token in tokens:
            token = token.strip()
            if token and token not in seen_tokens:  # Only process unique words
                token_id = wordToken(token)  # Generate token ID using wordToken function
                if is_title:
                    # Append "#" for tokens from the Title
                    token_ids.append(f"{token_id}#")
                else:
                    # Keep the token ID as is for the Tags
                    token_ids.append(str(token_id))  # Convert to string for consistency
                seen_tokens.add(token)  # Mark this token as processed
        return ', '.join(token_ids)

    # Initialize a list to store processed data
    processed_data = []

    # Process each row in the dataset
    for _, row in data.iterrows():
        # Process Title tokens (assuming Title tokens are separated by commas or spaces)
        title_tokens = process_text(row['Title'])  # Lemmatize the Title tokens
        title_token_ids = process_token_ids(title_tokens, is_title=True)

        # Process Tag tokens (assuming Tag tokens are separated by commas or spaces)
        tag_tokens = process_text(row['Tag'])  # Lemmatize the Tag tokens
        tag_token_ids = process_token_ids(tag_tokens, is_title=False)

        # Combine title and tag token IDs into one column
        combined_token_ids = f"{title_token_ids}, {tag_token_ids}" if title_token_ids or tag_token_ids else ''

        # Append the row's original data along with the combined token ID column
        processed_data.append({
            **row.to_dict(),  # Keep all original columns
            'combined_token_ids': combined_token_ids  # Add the combined token ID column
        })

    # Convert the processed data into a DataFrame
    processed_df = pd.DataFrame(processed_data)

    # Check if the output file exists and whether it is empty
    if os.path.exists(output_file_path):
        if os.stat(output_file_path).st_size == 0:  # Check if the file is empty
            processed_df.to_csv(output_file_path, index=False)  # Write with header if empty
            print(f"File was empty. Token IDs with headers have been written to {output_file_path}")
        else:
            # If the file exists and is not empty, append without headers
            processed_df.to_csv(output_file_path, mode='a', index=False, header=False)
            print(f"Token IDs have been appended to {output_file_path}")
    else:
        # If the file does not exist, write the file with header
        processed_df.to_csv(output_file_path, index=False)
        print(f"Token IDs have been written to {output_file_path}")

    # Function to remove duplicates and save to the file
    def remove_duplicates_and_save(output_file_path):
        # Check if the output file exists
        if os.path.exists(output_file_path):
            # Read the existing data from the output CSV file
            output_data = pd.read_csv(output_file_path)

            # Remove duplicates based on all columns (including 'combined_token_ids')
            cleaned_data = output_data.drop_duplicates()

            # Write the cleaned data back to the output file
            cleaned_data.to_csv(output_file_path, index=False)
            print(f"Duplicates removed and cleaned data saved to {output_file_path}")

    # Call the function to remove duplicates and save the cleaned data
    remove_duplicates_and_save(output_file_path)


process_data("./dataset/mdsample.csv", "./dataset/mdtokenssample.csv")
