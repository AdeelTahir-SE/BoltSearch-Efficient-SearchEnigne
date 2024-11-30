import pandas as pd
# Read the CSV files

dfT = pd.DataFrame(pd.read_csv('./server/jsondataset/Tags.csv', encoding='ISO-8859-1'))
dfQ = pd.DataFrame(pd.read_csv('./server/jsondataset/Questions.csv', encoding='ISO-8859-1'))
dfA = pd.DataFrame(pd.read_csv('./server/jsondataset/Answers.csv', encoding='ISO-8859-1'))

# Drop columns that are not needed
dfQ = dfQ.drop(columns=["OwnerUserId", "ClosedDate"])

# Merge the questions.csv and tags.csv
dfm = dfQ.merge(dfT, on="Id", how="left")

# Group the tags by Id and join them with a comma
dfm['Tag'] = dfm.groupby('Id')['Tag'].transform(
    lambda x: ','.join(str(tag) for tag in x.dropna().unique())
)
# Drop the duplicates after grouping
dfm = dfm.drop_duplicates(subset='Id', keep='first')

# Drop the columns that are not needed from the answers DataFrame
dfA = dfA.drop(columns=["Id","OwnerUserId", "CreationDate", "Score"])

# Rename the column ParentId to Id in the answers DataFrame
dfA.rename(columns={"ParentId": "Id", "Body": "Answer"}, inplace=True)

# Group the answers by Id and join them with a comma
dfA_grouped = dfA.groupby('Id')['Answer'].apply(lambda x: ',,,,,'.join(x.dropna().unique())).reset_index()

# Merge the answers DataFrame with the merged tags and questions DataFrame
dfm = dfm.merge(dfA_grouped, on='Id', how='left')

# Drop any duplicate rows based on the 'Id' column
dfm = dfm.drop_duplicates(subset='Id', keep='first')


# Save the merged DataFrame to a CSV file
dfm.to_csv("./server/jsondataset/Mergeddata.csv", index=False)

