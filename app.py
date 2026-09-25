from io import BytesIO
from pathlib import Path
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


st.set_page_config(
    page_title="SMOM Interactive",
    page_icon="⚓",
    layout="wide",
    initial_sidebar_state="expanded",
)

AS_OF_DATE = pd.Timestamp("2026-09-25")

SUPPORTED_TYPES = ["csv", "xlsx", "xls", "json", "parquet", "xml"]
@st.cache_data(show_spinner=False)
def read_upload(file_name, file_bytes):
    suffix = Path(file_name).suffix.lower()
    stream = BytesIO(file_bytes)

    if suffix == ".csv":
        for encoding in ("utf-8-sig", "cp1252", "latin1"):
            try:
                stream.seek(0)

                # Detect comma-, tab-, or semicolon-delimited source files.
                return pd.read_csv(
                    stream,
                    encoding=encoding,
                    sep=None,
                    engine="python",
                )

            except UnicodeDecodeError:
                continue

    if suffix in {".xlsx", ".xls"}:
        # Read the initial rows without headers so the program can find
        # the true row containing STATUS, VESSEL, LOCATION, etc.
        stream.seek(0)

        preview = pd.read_excel(
            stream,
            sheet_name=0,
            header=None,
            nrows=20,
        )

        header_row = 0

        required_header_terms = {
            "STATUS",
            "VESSEL",
            "LOCATION",
        }

        for row_index, row in preview.iterrows():
            row_values = {
                str(value).strip().upper()
                for value in row.dropna().tolist()
            }

            if required_header_terms.issubset(row_values):
                header_row = row_index
                break

        # Reload the workbook using the discovered header row.
        stream.seek(0)

        return pd.read_excel(
            stream,
            sheet_name=0,
            header=header_row,
        )

    if suffix == ".json":
        return pd.read_json(stream)

    if suffix == ".parquet":
        return pd.read_parquet(stream)

    if suffix == ".xml":
        return pd.read_xml(stream)

    raise ValueError(f"Unsupported file type: {suffix}")
