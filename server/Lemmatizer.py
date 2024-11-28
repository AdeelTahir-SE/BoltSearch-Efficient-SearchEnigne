import nltk
import pandas as pd
from nltk.stem import WordNetLemmatizer, PorterStemmer
from nltk import pos_tag, word_tokenize

# Download necessary NLTK resources
nltk.download('punkt')
nltk.download('averaged_perceptron_tagger')
nltk.download('wordnet')

# Initialize the lemmatizer and stemmer
lemmatizer = WordNetLemmatizer()
stemmer = PorterStemmer()

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

# Function to lemmatize and stem a word based on its POS tag
def process_word(word):
    # Tokenize the word and get the POS tag
    tokenized_word = word_tokenize(word)
    pos_tagged = pos_tag(tokenized_word)
    
    # Extract the POS tag
    word, tag = pos_tagged[0]
    
    # Get the WordNet POS tag
    wordnet_pos = get_wordnet_pos(tag)
    
    # Lemmatize and stem the word
    lemmatized_word = lemmatizer.lemmatize(word, wordnet_pos)
    stemmed_word = stemmer.stem(word)
    
    return lemmatized_word, stemmed_word

# Function to apply lemmatization and stemming to text
def apply_processing(text):
    words = text.split()  # Split the text into words
    lemmatized_words = []
    stemmed_words = []
    
    # Process each word
    for word in words:
        lemmatized_word, stemmed_word = process_word(word)
        lemmatized_words.append(lemmatized_word)
        stemmed_words.append(stemmed_word)
    
    # Join the lemmatized and stemmed words back into a string
    lemmatized_text = ' '.join(lemmatized_words)
    stemmed_text = ' '.join(stemmed_words)
    
    return lemmatized_text, stemmed_text

# Read the CSV file into DataFrame
MD = pd.read_csv('./server/jsondataset/Mergeddata.csv', encoding='ISO-8859-1')

# List of columns to exclude from processing
exclude_columns = ['Id', 'Score', 'CreationDate','Answer']

# Initialize lists to store lemmatized and stemmed texts for the whole DataFrame
lemmatized_column = []
stemmed_column = []

print('Processing text columns...')
# Iterate over each row and process all text columns
for index, row in MD.iterrows():
    lemmatized_row = []
    stemmed_row = []
    
    # Process each text column
    for column in MD.columns:
        if MD[column].dtype == 'object' and column not in exclude_columns:
            lemmatized_text, stemmed_text = apply_processing(row[column])
            lemmatized_row.append(lemmatized_text)
            stemmed_row.append(stemmed_text)
    
    # Join the processed texts (lemmatized and stemmed) for each row
    lemmatized_column.append(' '.join(lemmatized_row))
    stemmed_column.append(' '.join(stemmed_row))

# Add the new columns to the DataFrame
MD['Lemmatized'] = lemmatized_column
MD['Stemmed'] = stemmed_column

# Save the updated DataFrame with Lemmatized and Stemmed columns
MD.to_csv("./server/jsondataset/Lemmatizeddata.csv", index=False)

# Print the first few rows to verify the result
print(MD.head())
