import os
import pandas as pd

base_path = os.path.dirname(__file__)
file_path = os.path.join(base_path, "MEFMT_data (1).xlsx")
if not os.path.exists(file_path):
    raise FileNotFoundError("The master dataset MEFMT_data (1).xlsx was not found in the app folder.")
df = pd.read_excel(file_path)
