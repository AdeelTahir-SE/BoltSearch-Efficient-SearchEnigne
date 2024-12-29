
def final_Documents(documents):
    # Normalize and lemmatize the input words/phrases
    # Convert sorted DataFrame to a list of dictionaries (instead of tuples)
    result_dicts = [
        {
            'Id': row['Id'],
            'CreationDate': row['CreationDate'],
            'Score': row['Score'],
            'Title': row['Title'],
            'Body': row['Body'],
            'Tag': row['Tag'],
            'Answer': row['Answer'],
            'combined_token_ids': row['combined_token_ids'],
        }
        for _, row in documents.iterrows()
    ]
    
    return result_dicts
