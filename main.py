import os
import pandas as pd

base_path = os.path.dirname(__file__)
file_names = ['MSC Epic Fury Movement Tracker_N1.xlsx','MSC Epic Fury Movement Tracker_N1.csv','Epic Fury Data','clean_mcs.csv','CLEANED_JOINED_MODEL CRIT SCORE_DATA.csv']
file_path = next((os.path.join(base_path, name) for name in file_names if os.path.exists(os.path.join(base_path, name))), None)
if file_path is None:
    raise FileNotFoundError('No supported Epic Fury dataset was found in the app folder.')
df = pd.read_excel(file_path) if file_path.lower().endswith('.xlsx') else pd.read_csv(file_path)
