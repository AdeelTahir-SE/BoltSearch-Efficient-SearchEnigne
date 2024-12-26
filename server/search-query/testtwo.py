import pandas as pd
from collections import Counter
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize
import nltk
from datetime import datetime

# Initialize the WordNetLemmatizer
lemmatizer = WordNetLemmatizer()

def lemmatize_word(word):
    return lemmatizer.lemmatize(word)

def calculate_recency_weight(creation_date):
    try:
        today = datetime.today()
        creation_date = datetime.strptime(creation_date, '%Y-%m-%d')
        days_diff = (today - creation_date).days
        return 1 / (1 + days_diff)  # Newer dates get higher weight
    except Exception:
        return 0  # Return 0 weight for invalid dates

def rank_documents_by_words(documents, words, title_weight=2, score_weight=1, date_weight=1):
    # Normalize and lemmatize the input words/phrases
    lemmatized_phrases = [
        " ".join([lemmatize_word(word.lower()) for word in word_tokenize(phrase)]) for phrase in words
    ]
    def calculate_match_score(title):
        """
        Calculates match score based on the presence of lemmatized phrases in the title.
        :param title: Title of a document.
        :return: Match score (number of matched phrases).
        """
        if pd.isna(title):  # Handle missing titles
            return 0
        
        title = title.lower()  # Convert to lowercase
        title_tokens = [lemmatize_word(token) for token in word_tokenize(title)]  # Tokenize and lemmatize the title
        title_text = " ".join(title_tokens)  # Convert tokens back to a text string
        
        # Count the occurrences of each phrase
        match_count = sum(phrase in title_text for phrase in lemmatized_phrases)
        return match_count

    # Calculate title match score, recency weight, and overall score for each document
    documents['title_match_score'] = documents['Title'].apply(calculate_match_score)
    documents['recency_weight'] = documents['CreationDate'].apply(calculate_recency_weight)
    documents['weighted_score'] = (
        title_weight * documents['title_match_score'] +
        score_weight * documents['Score'] +
        date_weight * documents['recency_weight']
    )
    
    # Sort the DataFrame by 'weighted_score' (descending)
    ranked_documents = documents.sort_values(
        by=['weighted_score'], 
        ascending=False
    )
    
    # Convert sorted DataFrame to a list of tuples
    result_tuples = [
        (
            row['Id'],
            row['CreationDate'],
            row['Score'],
            row['Title'],
            row['Body'],
            row['Tag'],
            row['Answer'],
            row['combined_token_ids'],
            row['title_match_score'],
            row['recency_weight'],
            row['weighted_score']
        )
        for _, row in ranked_documents.iterrows()
    ]
    
    return result_tuples

# Example Usage:
if __name__ == "__main__":

    
    # Example DataFrame
    data = {
        'Id': [1, 2, 3, 4],
        'CreationDate': ['2024-01-01', '2023-12-25', '2024-01-05', '2023-12-30'],
        'Score': [100, 85, 90, 89],
        'Title': [
            "Introduction to AI and Machine Learning", 
            "Deep Learning Applications in AI", 
            "AI Trends 2024", 
            "Healthcare and AI"
        ],
        'Body': [
            "Detailed content about AI and ML.",
            "Focus on deep learning and its applications.",
            "Trends in AI for the year 2024.",
            "Use of AI in the healthcare industry."
        ],
        'Tag': ["AI, ML", "Deep Learning, AI", "AI, Trends", "AI, Healthcare"],
        'Answer': ["Answer1", "Answer2", "Answer3", "Answer4"],
        'combined_token_ids': ["1,2,3", "4,5,6", "7,8,9", "10,11,12"]
    }
    documents = pd.DataFrame(data)

    # Example multiword phrases to check
    words_to_check = ["AI and Healthcare"]
    
    # Rank documents
    ranked_docs = rank_documents_by_words(documents, words_to_check, title_weight=2, score_weight=1, date_weight=1)
    for doc in ranked_docs:
        print(doc)
