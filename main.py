import pandas as pd
import os

# Prefer the attached Epic Fury file, but keep compatibility with existing dataset names.
base_path = os.path.dirname(__file__)
csv_candidates = [
    'MSC Epic Fury Movement Tracker_N1.xlsx',
    'MSC Epic Fury Movement Tracker_N1.csv',
    'Epic Fury Data',
    'clean_mcs.csv',
    'CLEANED_JOINED_MODEL CRIT SCORE_DATA.csv',
]

file_path = next(
    (os.path.join(base_path, fname) for fname in csv_candidates if os.path.exists(os.path.join(base_path, fname))),
    None,
)
if file_path is None:
    raise FileNotFoundError(
        "Could not find the dataset file. Add 'MSC Epic Fury Movement Tracker_N1.csv' or the original CSV/XLSX to the app folder."
    )

if file_path.lower().endswith('.xlsx'):
    df = pd.read_excel(file_path)
else:
    df = pd.read_csv(file_path)
