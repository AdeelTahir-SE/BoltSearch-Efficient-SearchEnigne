import os
import sys
from datetime import datetime
import pandas as pd
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize

# Initialize the lemmatizer
lemmatizer = WordNetLemmatizer()


def filter_documents_by_title(documents, word):
    # Lemmatize the word for comparison
    word_lemma = lemmatizer.lemmatize(word.lower())
    
    # Define a function to lemmatize all words in a title
    def lemmatize_title(title):
        if pd.isna(title):  # Handle missing titles
            return ""
        words = word_tokenize(title.lower())  # Tokenize the title
        lemmatized_words = [lemmatizer.lemmatize(w) for w in words]  # Lemmatize each word
        return " ".join(lemmatized_words)  # Join back into a single string
    
    # Apply the lemmatization function to the 'title' column
    documents['lemmatized_title'] = documents['title'].apply(lemmatize_title)
    
    # Filter rows where the lemmatized title contains the lemmatized word
    filtered_documents = documents[documents['lemmatized_title'].str.contains(word_lemma, case=False, na=False)]
    
    # Drop the temporary lemmatized_title column before returning
    filtered_documents = filtered_documents.drop(columns=['lemmatized_title'])
    
    return filtered_documents

class Document:
    def _init_(self, title, score, creation_date):
        self.title = title
        self.score = score
        self.creation_date = creation_date

    def _repr_(self):
        return f"Document({self.title}, {self.score}, {self.creation_date})"


def rank_documents(documents, keyword, title_weight=0.5, score_weight=0.3, date_weight=0.2):
    def calculate_score(doc):
        # Title relevance: Count keyword occurrences in title
        title_relevance = doc.title.lower().count(keyword.lower())
        # Normalize title relevance
        title_relevance = min(title_relevance, 1)

        # Normalize score (assuming scores are out of 100)
        normalized_score = doc.score / 100.0

        # Date relevance: Newer documents get higher score
        days_old = (datetime.now() - doc.creation_date).days
        date_relevance = 1 / (1 + days_old)  # Inverse relation to age

        # Calculate weighted score
        total_score = (
            title_weight * title_relevance +
            score_weight * normalized_score +
            date_weight * date_relevance
        )
        return total_score

    ranked_documents = sorted(documents, key=calculate_score, reverse=True)
    return ranked_documents

# # Example usage:
# documents = [
#     Document('AI in Healthcare', 85, datetime(2023, 12, 1)),
#     Document('Deep Learning Applications', 90, datetime(2024, 1, 15)),
#     Document('AI Trends 2024', 78, datetime(2024, 10, 5)),
#     Document('Introduction to AI', 92, datetime(2022, 6, 10))
# ]

# keyword = 'AI'
# ranked_docs = rank_documents(documents, keyword)
# for doc in ranked_docs:
#     print(doc)
