from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="SMOM | Movement & Manpower Command Center",
    page_icon="⚓",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent
ARRIVAL_FILES = ["MEFMT_arrival_data (1).csv", "clean_mcs.csv", "MEFMT_data (1).xlsx"]
MODEL_FILES = ["CLEANED_JOINED_MODEL CRIT SCORE_DATA.csv"]

st.markdown(
    """
    <style>
    .stApp { background: radial-gradient(circle at top right,#123d61 0,#071a2f 42%,#061322 100%); color:#edf6ff; }
    .block-container { max-width:1500px; padding-top:1.5rem; }
    [data-testid="stSidebar"] { background:rgba(5,18,34,.96); border-right:1px solid rgba(255,255,255,.08); }
    [data-testid="stMetric"] { background:linear-gradient(145deg,rgba(31,76,111,.72),rgba(10,32,55,.9)); border:1px solid rgba(115,192,224,.18); border-radius:14px; padding:14px; }
    </style>
    """,
    unsafe_allow_html=True,
)

STATUS_COLORS = {
    "ON LOCATION": "#27ae60", "ARRIVED": "#27ae60", "PENDING": "#f39c12",
    "TRAVEL CONFIRMED": "#2980b9", "CANCELLED": "#c0392b", "NO SHOW": "#8e44ad",
    "IN TRANSIT": "#00a6b2", "STANDBY": "#8e44ad", "UNKNOWN": "#718096",
}


def first_existing(names):
    return next((BASE_DIR / name for name in names if (BASE_DIR / name).exists()), None)


def clean_columns(data):
    data = data.copy()
    data.columns = [str(c).strip() for c in data.columns]
    aliases = {
        "CIVMAR/PER": "PERSON", "EXT STATUS": "EXT_STATUS", "IN/OUT": "IN_OUT",
        "DATE 1": "DATE_1", "DATE 2": "DATE_2", "COMMENTS & ACTIONS": "COMMENTS",
        "Personnel_Type": "PERSONNEL_TYPE", "Pay_Grade_Level": "PAY_GRADE_LEVEL",
        "Model_Criticality_Score": "CRITICALITY_SCORE",
    }
    data = data.rename(columns=aliases)
    for column in data.columns:
        if data[column].dtype == "object":
            data[column] = data[column].replace(r"^\s*$", pd.NA, regex=True)
            data[column] = data[column].astype("string").str.strip()
    return data


def clean_arrivals(data):
    data = clean_columns(data)
    required = {"STATUS", "PERSON", "VESSEL", "LOCATION"}
    missing = required - set(data.columns)
    if missing:
        raise ValueError("Arrival data is missing: " + ", ".join(sorted(missing)))
    date_columns = ["START", "DATE_1", "DATE_2", "DOA", "DUE OFF DT", "LILP DATE"]
    for column in date_columns:
        if column in data:
            data[column] = pd.to_datetime(data[column], errors="coerce")
    for column in ["STATUS", "EXT_STATUS", "SEX", "RATING", "VESSEL", "LOCATION", "IN_OUT", "COMMENTS"]:
        if column in data:
            data[column] = data[column].fillna("Unknown").astype(str).str.strip().str.upper()
    data["STATUS"] = data["STATUS"].replace({"": "UNKNOWN", "NAN": "UNKNOWN"})
    data["PERSON"] = data["PERSON"].fillna("Unknown").astype(str).str.strip()
    data["SUCCESS"] = data["STATUS"].isin(["ARRIVED", "ON LOCATION"]).astype(int)
    data.insert(0, "SOURCE_ROW", range(2, len(data) + 2))
    return data


def clean_model(data):
    data = clean_columns(data)
    required = {"PERSONNEL_TYPE", "BSO", "PLATFORM", "JOB_SPECIALTY", "BA", "ONBOARD", "GAP", "CRITICALITY_SCORE"}
    missing = required - set(data.columns)
    if missing:
        raise ValueError("Manpower model data is missing: " + ", ".join(sorted(missing)))
    numeric = ["BA", "ONBOARD", "GAP", "CRITICALITY_SCORE"]
    for column in numeric:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    for column in data.columns:
        if data[column].dtype == "object" or str(data[column].dtype) == "string":
            data[column] = data[column].fillna("Unknown").astype(str).str.strip()
    data["STAFFING_STATE"] = data["GAP"].map(lambda value: "Shortage" if value > 0 else ("Surplus" if value < 0 else "Balanced"))
    return data


@st.cache_data
def read_file(path_str, uploaded_bytes=None, uploaded_name=""):
    if uploaded_bytes is not None:
        stream = BytesIO(uploaded_bytes)
        raw = pd.read_excel(stream) if uploaded_name.lower().endswith((".xlsx", ".xls")) else pd.read_csv(stream)
    else:
        path = Path(path_str)
        raw = pd.read_excel(path) if path.suffix.lower() in (".xlsx", ".xls") else pd.read_csv(path)
    return raw


def text_col(data, column):
    return data[column].fillna("Unknown").astype(str).str.upper() if column in data else pd.Series("UNKNOWN", index=data.index)


arrival_path = first_existing(ARRIVAL_FILES)
model_path = first_existing(MODEL_FILES)

with st.sidebar:
    st.header("Mission filters")
    arrival_upload = st.file_uploader("Replace arrival data", type=["csv", "xlsx", "xls"])
    model_upload = st.file_uploader("Replace manpower model", type=["csv", "xlsx", "xls"])

try:
    arrivals_raw = read_file(str(arrival_path), arrival_upload.getvalue() if arrival_upload else None, arrival_upload.name if arrival_upload else "") if arrival_path or arrival_upload else None
    model_raw = read_file(str(model_path), model_upload.getvalue() if model_upload else None, model_upload.name if model_upload else "") if model_path or model_upload else None
    arrivals = clean_arrivals(arrivals_raw) if arrivals_raw is not None else pd.DataFrame()
    model = clean_model(model_raw) if model_raw is not None else pd.DataFrame()
except (ValueError, pd.errors.ParserError, KeyError) as exc:
    st.error(f"Data validation failed: {exc}")
    st.stop()

if arrivals.empty and model.empty:
    st.error("No supported dataset was found. Add the arrival CSV and/or manpower model CSV to the repository.")
    st.stop()

st.title("⚓ SMOM Movement & Manpower Command Center")
st.caption("Cleaned arrival tracking, staffing gaps, and model criticality in one view")

with st.sidebar:
    st.divider()
    if not arrivals.empty:
        status_filter = st.selectbox("Arrival status", ["ALL"] + sorted(text_col(arrivals, "STATUS").unique()))
        vessel_filter = st.selectbox("Arrival vessel", ["ALL"] + sorted(text_col(arrivals, "VESSEL").unique()))
    else:
        status_filter = vessel_filter = "ALL"

filtered_arrivals = arrivals.copy()
if status_filter != "ALL":
    filtered_arrivals = filtered_arrivals[text_col(filtered_arrivals, "STATUS") == status_filter]
if vessel_filter != "ALL":
    filtered_arrivals = filtered_arrivals[text_col(filtered_arrivals, "VESSEL") == vessel_filter]

if not arrivals.empty:
    counts = text_col(filtered_arrivals, "STATUS").value_counts()
    success_rate = filtered_arrivals["SUCCESS"].mean() * 100 if len(filtered_arrivals) else 0
    metrics = [
        ("ARRIVAL RECORDS", len(filtered_arrivals)),
        ("SUCCESSFUL ARRIVALS", int(filtered_arrivals["SUCCESS"].sum())),
        ("SUCCESS RATE", f"{success_rate:.1f}%"),
        ("PENDING", int(counts.get("PENDING", 0))),
        ("TRAVEL CONFIRMED", int(counts.get("TRAVEL CONFIRMED", 0))),
    ]
    for column, (label, value) in zip(st.columns(len(metrics)), metrics):
        column.metric(label, value)

st.divider()

if not arrivals.empty:
    st.subheader("Arrival operations")
    left, right = st.columns(2)
    status_df = text_col(filtered_arrivals, "STATUS").value_counts().rename_axis("Status").reset_index(name="Count")
    status_fig = px.bar(status_df, x="Status", y="Count", color="Status", color_discrete_map=STATUS_COLORS, title="Arrival status")
    status_fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False)
    left.plotly_chart(status_fig, use_container_width=True)

    vessel_success = filtered_arrivals.groupby("VESSEL", dropna=False)["SUCCESS"].agg(["mean", "count"]).reset_index()
    vessel_success["Success rate (%)"] = vessel_success["mean"] * 100
    vessel_success = vessel_success.sort_values(["Success rate (%)", "count"], ascending=[False, False]).head(12)
    success_fig = px.bar(vessel_success, x="VESSEL", y="Success rate (%)", color="Success rate (%)", color_continuous_scale="Viridis", title="Arrival success rate by vessel")
    success_fig.update_yaxes(range=[0, 100])
    success_fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    right.plotly_chart(success_fig, use_container_width=True)

if not model.empty:
    st.subheader("Manpower model")
    model_left, model_right = st.columns(2)
    gap_summary = model.groupby("BSO", dropna=False)[["BA", "ONBOARD"]].sum().reset_index()
    gap_summary["Net gap"] = gap_summary["BA"] - gap_summary["ONBOARD"]
    gap_fig = px.bar(gap_summary.sort_values("Net gap"), x="BSO", y="Net gap", color="Net gap", color_continuous_scale="RdYlGn", title="Net staffing gap by BSO")
    gap_fig.add_hline(y=0, line_dash="dash", line_color="white")
    gap_fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    model_left.plotly_chart(gap_fig, use_container_width=True)

    criticality = model.groupby("JOB_SPECIALTY", dropna=False)["CRITICALITY_SCORE"].mean().reset_index().sort_values("CRITICALITY_SCORE", ascending=False)
    criticality_fig = px.bar(criticality.head(12), x="CRITICALITY_SCORE", y="JOB_SPECIALTY", orientation="h", color="CRITICALITY_SCORE", color_continuous_scale="Magma", title="Average criticality by specialty")
    criticality_fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    model_right.plotly_chart(criticality_fig, use_container_width=True)

st.divider()
tab_arrivals, tab_model, tab_quality = st.tabs(["📋 Clean arrival roster", "📊 Clean manpower model", "✅ Data quality"])

with tab_arrivals:
    if arrivals.empty:
        st.info("No arrival dataset loaded.")
    else:
        view = filtered_arrivals.copy()
        for column in view.columns:
            if pd.api.types.is_datetime64_any_dtype(view[column]):
                view[column] = view[column].dt.strftime("%Y-%m-%d")
        st.dataframe(view, use_container_width=True, hide_index=True)
        st.download_button("Download cleaned arrivals", view.to_csv(index=False).encode("utf-8"), "cleaned_arrivals.csv", "text/csv")

with tab_model:
    if model.empty:
        st.info("No manpower model dataset loaded.")
    else:
        st.dataframe(model, use_container_width=True, hide_index=True)
        st.download_button("Download cleaned manpower model", model.to_csv(index=False).encode("utf-8"), "cleaned_manpower_model.csv", "text/csv")

with tab_quality:
    st.write({
        "arrival_source": arrival_upload.name if arrival_upload else (arrival_path.name if arrival_path else "not loaded"),
        "arrival_rows": len(arrivals),
        "arrival_columns": len(arrivals.columns),
        "model_source": model_upload.name if model_upload else (model_path.name if model_path else "not loaded"),
        "model_rows": len(model),
        "model_columns": len(model.columns),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    })
    st.info("Blank text fields are standardized to Unknown, dates are parsed safely, numeric model fields are coerced, and derived success/staffing-state fields are added.")
