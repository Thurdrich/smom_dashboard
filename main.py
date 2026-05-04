import pandas as pd
import os

# This ensures the app finds the CSV regardless of how it is launched
base_path = os.path.dirname(__file__)
csv_candidates = [
    'clean_mcs.csv',
    'CLEANED_JOINED_MODEL CRIT SCORE_DATA.csv'
]
csv_path = next(
    (os.path.join(base_path, fname) for fname in csv_candidates if os.path.exists(os.path.join(base_path, fname))),
    None
)
if csv_path is None:
    raise FileNotFoundError(
        "Could not find the dataset file. Add 'clean_mcs.csv' or the existing CSV file to the app folder."
    )
df = pd.read_csv(csv_path)
