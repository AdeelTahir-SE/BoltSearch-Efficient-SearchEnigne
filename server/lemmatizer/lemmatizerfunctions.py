import nltk
import pandas as pd
from nltk.stem import WordNetLemmatizer
from nltk import pos_tag, word_tokenize
import os

# Download necessary NLTK resources
nltk.download('punkt')
nltk.download('averaged_perceptron_tagger')
nltk.download('wordnet')

# Initialize the lemmatizer
lemmatizer = WordNetLemmatizer()

# Function to get WordNet POS tag from Penn Treebank POS tag
def get_wordnet_pos(tag):
    if tag.startswith('J'):
        return 'a'  # Adjective
    elif tag.startswith('V'):
        return 'v'  # Verb
    elif tag.startswith('N'):
        return 'n'  # Noun
    elif tag.startswith('R'):
        return 'r'  # Adverb
    else:
        return 'n'  # Default to noun

# Function to lemmatize a word based on its POS tag
def lemmatize_word(word):
    tokenized_word = word_tokenize(word)
    pos_tagged = pos_tag(tokenized_word)
    word, tag = pos_tagged[0]
    wordnet_pos = get_wordnet_pos(tag)
    return lemmatizer.lemmatize(word, wordnet_pos)

# Function to apply lemmatization to text
def apply_processing(text):
    tokenized_words = word_tokenize(text)  # Tokenize the text
    pos_tagged = pos_tag(tokenized_words)  # Get POS tags
    
    lemmatized_words = []
    
    # Lemmatize each word based on its POS tag
    for word, tag in pos_tagged:
        wordnet_pos = get_wordnet_pos(tag)  # Map to WordNet POS
        lemmatized_word = lemmatizer.lemmatize(word, wordnet_pos)
        lemmatized_words.append(lemmatized_word)
    
    # Join the lemmatized words back into a string
    lemmatized_text = ' '.join(lemmatized_words)
    
    return lemmatized_text

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



def remove_duplicates_and_save(file_path):
 
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return
    
    # Load the existing file
    df = pd.read_csv(file_path, encoding='ISO-8859-1')
    
    # Check if the necessary columns exist in the dataframe
    if 'id' not in df.columns or 'lemmatizedtag' not in df.columns:
        print("Required columns ('id', 'lemmatizedtag') are missing from the file.")
        return

    # Remove duplicates based on 'id' and 'lemmatizedtag' columns
    df_cleaned = df.drop_duplicates(subset=['id', 'lemmatizedtag'])

    # Write the cleaned data back to the same file
    df_cleaned.to_csv(file_path, index=False)

    print(f"Duplicates removed and data saved back to {file_path}.")



