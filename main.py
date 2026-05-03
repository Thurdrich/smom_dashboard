import pandas as pd
import os

# This ensures the app finds the CSV regardless of how it is launched
base_path = os.path.dirname(__file__)
csv_path = os.path.join(base_path, 'clean_mcs.csv')
df = pd.read_csv(csv_path)