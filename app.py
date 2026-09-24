import streamlit as st
import pandas as pd
import plotly.express as px
import os
from pathlib import Path

st.set_page_config(page_title="Epic Fury Movement Tracker", page_icon="🚢", layout="wide")

st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(180deg, #071a2f 0%, #0d2748 100%);
        color: #edf6ff;
    }
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    [data-testid="stSidebar"] {
        background: rgba(12, 31, 52, 0.9);
    }
    div[data-testid="stMetric"] {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        padding: 0.8rem 1rem;
        border-radius: 0.75rem;
    }
    h1, h2, h3 {
        color: #f0f7ff;
    }
    .stDataFrame {
        background: rgba(255,255,255,0.02);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_tracker_data():
    base_dir = Path(__file__).resolve().parent
    candidates = [
        "MSC Epic Fury Movement Tracker_N1.xlsx",
        "MSC Epic Fury Movement Tracker_N1.csv",
        "Epic Fury Data",
        "clean_mcs.csv",
        "CLEANED_JOINED_MODEL CRIT SCORE_DATA.csv",
    ]

    file_path = None
    for candidate in candidates:
        p = base_dir / candidate
        if p.exists():
            file_path = p
            break

    if file_path is None:
        return None

    if file_path.suffix.lower() == ".xlsx":
        df = pd.read_excel(file_path)
    else:
        df = pd.read_csv(file_path)

    df.columns = [str(col).strip() for col in df.columns]

    # Standardize a few common field names for compatibility with legacy files.
    rename_map = {
        "CIVMAR/PER": "CIVMAR_PER",
        "CIVMAR IN/OUT": "CIVMAR_IN_OUT",
        "COMMENTS & ACTIONS": "COMMENTS_ACTIONS",
        "DUE OFF DT": "DUE_OFF_DT",
        "LILP SHP": "LILP_SHP",
        "LILP DATE": "LILP_DATE",
        "EXT STATUS": "EXT_STATUS",
        "IN/OUT": "IN_OUT",
        "DOA": "DOA",
        "O/D": "OD",
        "STATUS": "STATUS",
        "LOCATION": "LOCATION",
        "VESSEL": "VESSEL",
        "SEX": "SEX",
        "RATING": "RATING",
        "START": "START",
        "LEG 1": "LEG_1",
        "DATE 1": "DATE_1",
        "LEG 2": "LEG_2",
        "DATE 2": "DATE_2",
        "Personnel_Type": "Personnel_Type",
        "BSO": "BSO",
        "Platform": "Platform",
        "Job_Specialty": "Job_Specialty",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    for col in ["STATUS", "EXT_STATUS", "LOCATION", "VESSEL", "SEX", "RATING", "START", "IN_OUT"]:
        if col in df.columns:
            df[col] = df[col].fillna("Unknown").astype(str).str.strip()

    for col in ["DATE_1", "DATE_2", "DOA", "DUE_OFF_DT", "LILP_DATE"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    if "STATUS" in df.columns:
        df["STATUS"] = df["STATUS"].str.upper().replace({"N/A": "UNKNOWN", "nan": "UNKNOWN"})

    if "OD" in df.columns:
        df["OD"] = pd.to_numeric(df["OD"], errors="coerce")

    return df


try:
    df = load_tracker_data()
except Exception:
    df = None

if df is None:
    st.error("No supported dataset file was found. Add 'MSC Epic Fury Movement Tracker_N1.csv' or the original CSV/XLSX to this folder.")
    st.stop()

# Sidebar filters
with st.sidebar:
    st.header("Filters")

    status_options = ["All"] + sorted(
        pd.Series(df["STATUS"].dropna().astype(str).str.upper().unique()).tolist(),
        key=lambda x: str(x),
    ) if "STATUS" in df.columns else ["All"]
    selected_status = st.selectbox("Status", status_options)

    location_options = ["All"] + sorted(
        pd.Series(df["LOCATION"].dropna().astype(str).str.upper().unique()).tolist(),
        key=lambda x: str(x),
    ) if "LOCATION" in df.columns else ["All"]
    selected_location = st.selectbox("Location", location_options)

    vessel_options = ["All"] + sorted(
        pd.Series(df["VESSEL"].dropna().astype(str).str.upper().unique()).tolist(),
        key=lambda x: str(x),
    ) if "VESSEL" in df.columns else ["All"]
    selected_vessel = st.selectbox("Vessel", vessel_options)

    sex_options = ["All"] + sorted(
        pd.Series(df["SEX"].dropna().astype(str).str.upper().unique()).tolist(),
        key=lambda x: str(x),
    ) if "SEX" in df.columns else ["All"]
    selected_sex = st.selectbox("Sex", sex_options)

    st.markdown("---")
    st.caption("Epic Fury dashboard")

# Filter data
filtered = df.copy()
if selected_status != "All" and "STATUS" in filtered.columns:
    filtered = filtered[filtered["STATUS"].astype(str).str.upper() == selected_status]
if selected_location != "All" and "LOCATION" in filtered.columns:
    filtered = filtered[filtered["LOCATION"].astype(str).str.upper() == selected_location]
if selected_vessel != "All" and "VESSEL" in filtered.columns:
    filtered = filtered[filtered["VESSEL"].astype(str).str.upper() == selected_vessel]
if selected_sex != "All" and "SEX" in filtered.columns:
    filtered = filtered[filtered["SEX"].astype(str).str.upper() == selected_sex]

# KPI summary
status_counts = filtered["STATUS"].astype(str).str.upper().value_counts() if "STATUS" in filtered.columns else pd.Series(dtype=int)

summary = {
    "Total": len(filtered),
    "On Location": int(status_counts.get("ON LOCATION", 0)),
    "Pending": int(status_counts.get("PENDING", 0)),
    "Travel Confirmed": int(status_counts.get("TRAVEL CONFIRMED", 0)),
    "Cancelled": int(status_counts.get("CANCELLED", 0)),
    "No Show": int(status_counts.get("NO SHOW", 0)),
}

st.title("Epic Fury Movement Tracker")
st.caption("Live personnel movement, travel status, and duty tracker")

cols = st.columns(6)
for i, (label, value) in enumerate(summary.items()):
    cols[i].metric(label, value)

st.markdown("---")

# Charts
left, right = st.columns(2)

if "STATUS" in filtered.columns:
    status_df = filtered["STATUS"].astype(str).str.upper().value_counts().reset_index()
    status_df.columns = ["Status", "Count"]
    fig = px.bar(status_df, x="Status", y="Count", color="Status", title="Movement status by count")
    fig.update_layout(showlegend=False, template="plotly_dark")
    left.plotly_chart(fig, use_container_width=True)

if "LOCATION" in filtered.columns:
    loc_df = filtered["LOCATION"].fillna("Unknown").astype(str).str.upper().value_counts().head(10).reset_index()
    loc_df.columns = ["Location", "Count"]
    fig2 = px.bar(loc_df, x="Count", y="Location", orientation="h", color="Location", title="Top locations")
    fig2.update_layout(showlegend=False, template="plotly_dark")
    right.plotly_chart(fig2, use_container_width=True)

if "VESSEL" in filtered.columns:
    vessel_df = filtered["VESSEL"].fillna("Unknown").astype(str).str.upper().value_counts().head(10).reset_index()
    vessel_df.columns = ["Vessel", "Count"]
    fig3 = px.pie(vessel_df, names="Vessel", values="Count", title="Assignments by vessel")
    fig3.update_layout(template="plotly_dark")
    left.plotly_chart(fig3, use_container_width=True)

if "RATING" in filtered.columns:
    rating_df = filtered["RATING"].fillna("Unknown").astype(str).str.upper().value_counts().head(12).reset_index()
    rating_df.columns = ["Rating", "Count"]
    fig4 = px.bar(rating_df, x="Rating", y="Count", title="Personnel by rating")
    fig4.update_layout(template="plotly_dark")
    right.plotly_chart(fig4, use_container_width=True)

st.markdown("---")

# Data table
st.subheader("Roster / movement detail")

preferred_cols = [
    c for c in [
        "STATUS",
        "EXT_STATUS",
        "SEX",
        "CIVMAR_PER",
        "RATING",
        "VESSEL",
        "LOCATION",
        "START",
        "IN_OUT",
        "DOA",
        "DUE_OFF_DT",
        "OD",
        "COMMENTS_ACTIONS",
    ] if c in filtered.columns
]

if preferred_cols:
    display = filtered[preferred_cols].copy()
    for col in ["DOA", "DUE_OFF_DT"]:
        if col in display.columns:
            display[col] = display[col].dt.strftime("%Y-%m-%d")
    st.dataframe(display.head(250), use_container_width=True, hide_index=True)
else:
    st.dataframe(filtered.head(250), use_container_width=True, hide_index=True)

csv_data = filtered.to_csv(index=False).encode("utf-8")
st.download_button("Download filtered dataset", csv_data, file_name="epic_fury_filtered.csv", mime="text/csv")

""" 
{"path":"main.py","ref":"main","repo":"Thurdrich/smom_dashboard"} """:
    pass


# keep a minimal script-friendly loader for local execution and direct imports
if __name__ == "__main__":
    pass




















































































































































































