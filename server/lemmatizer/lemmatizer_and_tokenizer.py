import pandas as pd
import re
from lemmatizerfunctions import lemmatize_word, wordToken,remove_duplicates_and_save
import os

# File paths
input_file_path = r'server\jsondataset\Mergeddata.csv'
lemmatized_file_path = r'server\jsondataset\LemmatizedTags&Tokens.csv'

# Check if the lemmatized file exists; if not, create it
if not os.path.exists(lemmatized_file_path) or os.stat(lemmatized_file_path).st_size == 0:
    pd.DataFrame(columns=['id', 'lemmatizedtag']).to_csv(lemmatized_file_path, index=False)

# Read the dataset
data = pd.read_csv(input_file_path, encoding='ISO-8859-1')

# Helper function to lemmatize and split text
def process_text(text):
    if not isinstance(text, str):  # Handle NaN or None values
        return []
    tokens = re.split(r'[ ,]', text)
    return [lemmatize_word(token.strip()) for token in tokens if token.strip()]

# Initialize a list to store the new lemmatized data
lemmatized_data = []

# Process each row in the dataset
for _, row in data.iterrows():
    lemmatized_title = process_text(row['Title'])
    if lemmatized_title:
        for word in lemmatized_title:
            word_id = wordToken(word)
            lemmatized_data.append({'id': f"{word_id}#", 'lemmatizedtag': word.lower()})

    lemmatized_tags = process_text(row['Tag'])
    if lemmatized_tags:
        for word in lemmatized_tags:
            word_id = wordToken(word)
            lemmatized_data.append({'id': str(word_id), 'lemmatizedtag': word.lower()})

# Convert the new lemmatized data into a DataFrame
lemmatized_df = pd.DataFrame(lemmatized_data)

# Normalize the data
lemmatized_df['id'] = lemmatized_df['id'].str.strip()
lemmatized_df['lemmatizedtag'] = lemmatized_df['lemmatizedtag'].str.strip().str.lower()

# Load only the unique identifiers from the existing file
existing_ids = set()
existing_tags = set()

with open(lemmatized_file_path, 'r', encoding='ISO-8859-1') as f:
    # Skip the header line and extract unique ids and tags
    for line in f.readlines()[1:]:
        parts = line.strip().split(',')
        if len(parts) == 2:
            existing_ids.add(parts[0].strip())
            existing_tags.add(parts[1].strip().lower())

# Filter out duplicates by checking against existing IDs and Tags
lemmatized_df = lemmatized_df[
    ~lemmatized_df['id'].isin(existing_ids) | ~lemmatized_df['lemmatizedtag'].isin(existing_tags)
]

# Append only the new unique rows to the file
lemmatized_df.to_csv(lemmatized_file_path, mode='a', index=False, header=False)
remove_duplicates_and_save(lemmatized_file_path)
print("Lemmatized data has been appended with uniqueness ensured.")


