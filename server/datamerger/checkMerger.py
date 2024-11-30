import pandas as pd

# Read the CSV file into the DataFrame
df = pd.read_csv('server/jsondataset/Mergeddata_with_combined_tokenids.csv')

print(df.columns)
print(df.head())
