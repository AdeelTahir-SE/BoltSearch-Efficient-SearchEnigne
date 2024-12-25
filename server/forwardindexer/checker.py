import pandas as pd

# Read the CSV file into the DataFrame
df = pd.read_csv('server/jsondataset/Mergeddata_with_tokens.csv')

print(df.columns)
head=df.head()
print(head)

file=open('index.csv','w')
file.write(head)
