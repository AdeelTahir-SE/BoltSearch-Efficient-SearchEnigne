import pandas as pd
dfT=pd.DataFrame(pd.read_csv('./server/jsondataset/Tags.csv', encoding='ISO-8859-1'))
dfQ=pd.DataFrame(pd.read_csv('./server/jsondataset/Questions.csv', encoding='ISO-8859-1'))
dfA=pd.DataFrame(pd.read_csv('./server/jsondataset/Answers.csv', encoding='ISO-8859-1'))


# drops the columns that are not needed
dfQ=dfQ.drop(columns=["OwnerUserId","ClosedDate"])

# merges the questions.csv and tags.csv
dfm=dfQ.merge(dfT,on="Id",how="left")

# groups the tags by Id and joins them with a comma
dfm['Tag'] = dfm.groupby('Id')['Tag'].transform(
    lambda x: ','.join(str(tag) for tag in x.dropna().unique())
)

# drops the duplicates
dfm=dfm.drop_duplicates(subset='Id', keep='first',)

# drops the columns that are not needed
dfA=dfA.drop(columns=["OwnerUserId","CreationDate","Score"])

# renames the column ParentId to Id
dfA.reanme(columns={"ParentId":"Id","Body":"Answer"},inplace=True)

# merges the answers dataframe with the merged dataframe
dfm=dfm.merge(dfA,on='Id',how="left")

# groups the answers by Id and joins them with a comma
dfm['Answer'] = dfm.groupby('Id')['Answer'].transform(
    lambda x: ','.join(str(body) for body in x.dropna().unique())
)

# drops the duplicates
dfm=dfm.drop_duplicates(subset='Id', keep='first',)

print(dfm.head())
print(dfm.columns)

# saves the merged dataframe to a csv file
dfm.to_csv("./server/jsondataset/merged.csv",index=False)