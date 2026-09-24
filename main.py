import pandas as pd
import os

# Prefer the newly attached Epic Fury dataset but keep compatibility with the older filenames.
base_path = os.path.dirname(__file__)
csv_candidates = [
    'MSC Epic Fury Movement Tracker_N1.xlsx',
    'MSC Epic Fury Movement Tracker_N1.csv',
    'Epic Fury Data',
    'clean_mcs.csv',
    'CLEANED_JOINED_MODEL CRIT SCORE_DATA.csv'
]

csv_path = next(
    (os.path.join(base_path, fname) for fname in csv_candidates if os.path.exists(os.path.join(base_path, fname))),
    None
)
if csv_path is None:
    raise FileNotFoundError(
        "Could not find the dataset file. Add 'MSC Epic Fury Movement Tracker_N1.csv' or the existing CSV file to the app folder."
    )

if csv_path.lower().endswith('.xlsx'):
    df = pd.read_excel(csv_path)
else:
    df = pd.read_csv(csv_path)
