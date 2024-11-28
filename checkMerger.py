import pandas as pd

# Read the CSV file into the DataFrame
df = pd.read_csv('./server/jsondataset/Mergeddata.csv')

# Set pandas options to display all columns without truncation
pd.set_option('display.max_columns', None)  # Show all columns
pd.set_option('display.width', None)  # Prevent truncation of rows

# Open the file for writing
with open("index.txt", 'w') as file:
    # Write the first five rows of the DataFrame to the file as a string
    file.write(df.head(5).to_string(index=False))  # Convert the first five rows to string and write it
