import pandas as pd
from collections import Counter
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize
import nltk
from datetime import datetime

# Initialize the WordNetLemmatizer
lemmatizer = WordNetLemmatizer()

def lemmatize_word(word):
    """
    Lemmatize a single word using WordNetLemmatizer.
    """
    return lemmatizer.lemmatize(word)

def calculate_recency_weight(creation_date):
    """
    Assign a weight to documents based on how recent their CreationDate is.
    :param creation_date: String date in ISO 8601 format ('YYYY-MM-DDTHH:mm:ssZ') or 'YYYY-MM-DD'.
    :return: A weight (higher for newer dates).
    """
    try:
        # Handle both ISO 8601 and 'YYYY-MM-DD' formats
        if 'T' in creation_date and 'Z' in creation_date:
            creation_date = datetime.strptime(creation_date, '%Y-%m-%dT%H:%M:%SZ')
        else:
            creation_date = datetime.strptime(creation_date, '%Y-%m-%d')

        today = datetime.utcnow()  # Use UTC for consistency
        print(f"Current date: {today}")  # Debugging line

        # Calculate the difference between the current date and the creation date
        days_diff = (today - creation_date).days
        print(f"Days difference: {days_diff}")  # Debugging line

        # Return a weight based on the difference (newer dates get higher weight)
        return 1 / (1 + days_diff) if days_diff >= 0 else 0  # Ensure non-negative weights

    except Exception as e:
        print(f"Error parsing date: {e}")
        return 0  # Return 0 weight for invalid dates


def rank_documents_by_words(documents, words, title_weight=2, score_weight=1, date_weight=1):
    """
    Ranks documents based on weighted combination of Title, Score, and CreationDate.

    :param documents: Pandas DataFrame with columns 'Id', 'CreationDate', 'Score', 'Title', 'Body', 'Tag', 'Answer', 'combined_token_ids'.
    :param words: List of words to search for in the document titles.
    :param title_weight: Weight assigned to the title word match score.
    :param score_weight: Weight assigned to the document score.
    :param date_weight: Weight assigned to the recency of the document.
    :return: List of tuples representing ranked documents.
    """
    # Lemmatize the input words
    lemmatized_words = [lemmatize_word(word.lower()) for word in words]
    
    def calculate_match_score(title):
        """
        Calculates match score and checks if all words are present in the title.
        :param title: Title of a document.
        :return: Matched word count.
        """
        if pd.isna(title):  # Handle missing titles
            return 0
        
        title = title.lower()  # Convert to lowercase
        title_tokens = [lemmatize_word(token) for token in word_tokenize(title)]  # Tokenize and lemmatize the title
        title_counter = Counter(title_tokens)  # Count occurrences of tokens
        
        # Count matched words
        matched_word_count = sum(title_counter[word] > 0 for word in lemmatized_words)
        return matched_word_count

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

# # Example Usage:
# if __name__ == "__main__":

#     # Example DataFrame
#     data = {
#         'Id': [1, 2, 3, 4],
#         'CreationDate': ['2024-01-01', '2023-12-25', '2024-01-05', '2023-12-30'],
#         'Score': [100, 85, 90, 98],
#         'Title': [
#             "Introduction to AI and Machine Learning", 
#             "Deep Learning Applications in AI", 
#             "AI Trends 2024", 
#             "Healthcare and AI"
#         ],
#         'Body': [
#             "Detailed content about AI and ML.",
#             "Focus on deep learning and its applications.",
#             "Trends in AI for the year 2024.",
#             "Use of AI in the healthcare industry."
#         ],
#         'Tag': ["AI, ML", "Deep Learning, AI", "AI, Trends", "AI, Healthcare"],
#         'Answer': ["Answer1", "Answer2", "Answer3", "Answer4"],
#         'combined_token_ids': ["1,2,3", "4,5,6", "7,8,9", "10,11,12"]
#     }
#     documents = pd.DataFrame(data)

#     # Example words to check
#     words_to_check = ["Healthcare"]
    
#     # Rank documents
#     ranked_docs = rank_documents_by_words(documents, words_to_check, title_weight=2, score_weight=1, date_weight=1)
#     for doc in ranked_docs:
#         print(doc)
