import pandas as pd
import os
import csv
from collections import defaultdict

# Load the DataFrame from the CSV
brls = pd.read_csv("./Barrels/Mergeddata.csv")

# Convert the DataFrame rows to a list of tuples (excluding the index)
tuple_list = list(brls.itertuples(index=False, name=None))

# Extract the QuestionID column as a list
QuestionsID = brls["Id"].tolist()

# Sort the QuestionID
QuestionsID.sort()

# Set the barrel size and total number of records
barrel_size = 4000
total_records = len(QuestionsID)

# Create a dictionary to store rows for each barrel range
barrels = defaultdict(list)

# Loop over the QuestionIDs and store the corresponding row in the appropriate barrel
for question_id, row in zip(QuestionsID, tuple_list):
    # Calculate the barrel number by finding which range the QuestionID falls into
    barrel_number = (question_id // barrel_size) * barrel_size
    
    # Store the row in the respective barrel
    barrels[barrel_number].append(row)

# Create the output directory if it doesn't exist
output_dir = "./Barrels"
os.makedirs(output_dir, exist_ok=True)

# Write each barrel's content to a CSV file
for barrel_number, rows in barrels.items():
    file_name = os.path.join(output_dir, f"barrel_{barrel_number}_to_{barrel_number + barrel_size - 1}.csv")
    
    # Write the rows to the CSV file with UTF-8 encoding, ignoring problematic characters
    with open(file_name, 'w', newline='', encoding='utf-8', errors='ignore') as f:
        writer = csv.writer(f)
        
        # Write the header (use the column names from the original DataFrame)
        writer.writerow(brls.columns)
        
        # Write the rows belonging to this barrel
        writer.writerows(rows)

print("Barrel files created successfully!")
