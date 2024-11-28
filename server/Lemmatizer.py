import pyarrow.parquet as pq
import pyarrow as pa
import pandas as pd
import nltk
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer
from joblib import Parallel, delayed

# Initialize the lemmatizer
lemmatizer = WordNetLemmatizer()

# Function to process and lemmatize text
def process_column(column):
    return column.apply(lambda text: ' '.join(
        [lemmatizer.lemmatize(word) for word in word_tokenize(text)] if pd.notnull(text) else ''
    ))

# Function to read Parquet file
def process_parquet_file(file_path):
    table = pq.read_table(file_path)
    return table.to_pandas()

# Function to lemmatize and save
# Function to process and lemmatize text


# Function to lemmatize and save
def lemmatize_and_save_optimized():
    # File paths
    input_file_path = './server/jsondataset/FinalMergedData.parquet'
    output_file_path = './server/jsondataset/Lemmatized_FinalMergedData.parquet'

    # Load data
    df = process_parquet_file(input_file_path)
    print("Columns in the DataFrame:", df.columns)

    # Replace NaN or None values with empty strings
    df.fillna('', inplace=True)

    # Columns to lemmatize
    columns_to_lemmatize = ['Title', 'Body_Question', 'Tags', 'Answer_Details']

    # Apply lemmatization using parallel processing
    lemmatized_columns = Parallel(n_jobs=8)(
        delayed(process_column)(df[col]) for col in columns_to_lemmatize if col in df.columns
    )

    # Add lemmatized columns back to the DataFrame
    for col, lemmatized_col in zip(columns_to_lemmatize, lemmatized_columns):
        df[f'lemmatized_{col.lower()}'] = lemmatized_col

    # Save the lemmatized DataFrame to a Parquet file
    table = pa.Table.from_pandas(df)
    pq.write_table(table, output_file_path)

    print(f"Lemmatized data has been written to {output_file_path}")

# Run the script
lemmatize_and_save_optimized()