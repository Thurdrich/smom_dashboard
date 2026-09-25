from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="SMOM | Strategic Insight Studio",
    page_icon="⚓",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp { background: radial-gradient(circle at top right,#123d61 0,#071a2f 42%,#061322 100%); color:#edf6ff; }
    .block-container { max-width:1500px; padding-top:1.5rem; }
    [data-testid="stSidebar"] { background:rgba(5,18,34,.96); border-right:1px solid rgba(255,255,255,.08); }
    [data-testid="stMetric"] { background:linear-gradient(145deg,rgba(31,76,111,.72),rgba(10,32,55,.9)); border:1px solid rgba(115,192,224,.18); border-radius:14px; padding:14px; }
    .insight { background:rgba(22,65,92,.58); border-left:4px solid #49c6c8; border-radius:8px; padding:14px 18px; }
    </style>
    """,
    unsafe_allow_html=True,
)

SUPPORTED_TYPES = ["csv", "xlsx", "xls", "json"]
DEMO_ROWS = 180


def demo_data():
    """A useful preview that makes the app understandable before an upload."""
    rng = np.random.default_rng(7)
    dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=DEMO_ROWS, freq="D")
    regions = rng.choice(["North", "South", "East", "West"], DEMO_ROWS)
    workload = rng.normal(72, 18, DEMO_ROWS).clip(10, 140).round(1)
    staffing = (workload * rng.normal(0.91, 0.12, DEMO_ROWS)).clip(5, 150).round(1)
    return pd.DataFrame({
        "Date": dates, "Region": regions, "Workload": workload,
        "Staffing": staffing, "Readiness": (100 - (workload - staffing).clip(0) * 1.7).clip(35, 100).round(1),
        "Priority": rng.choice(["Routine", "Elevated", "Critical"], DEMO_ROWS, p=[.55, .3, .15]),
    })


@st.cache_data(show_spinner=False)
def read_upload(file_name, file_bytes):
    suffix = Path(file_name).suffix.lower()
    stream = BytesIO(file_bytes)
    if suffix == ".csv":
        return pd.read_csv(stream)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(stream)
    if suffix == ".json":
        return pd.read_json(stream)
    raise ValueError(f"Unsupported file type: {suffix}")


def load_uploads(files):
    frames = []
    errors = []
    for uploaded in files or []:
        try:
            frame = read_upload(uploaded.name, uploaded.getvalue()).copy()
            frame.columns = [str(c).strip() or f"Column {i + 1}" for i, c in enumerate(frame.columns)]
            frame["Source file"] = uploaded.name
            frames.append(frame)
        except Exception as exc:  # show one bad file without losing valid files
            errors.append(f"{uploaded.name}: {exc}")
    if not frames:
        return pd.DataFrame(), errors
    return pd.concat(frames, ignore_index=True, sort=False), errors


def profile(data):
    numeric = data.select_dtypes(include="number").columns.tolist()
    dates = []
    for column in data.columns:
        if column == "Source file" or pd.api.types.is_numeric_dtype(data[column]):
            continue
        parsed = pd.to_datetime(data[column], errors="coerce")
        if parsed.notna().mean() >= 0.7:
            dates.append(column)
    categorical = [c for c in data.columns if c not in numeric and c not in dates]
    return numeric, dates, categorical


def chart_frame(data, numeric, dates, categorical):
    """Build four adaptive charts; each one gracefully falls back for sparse data."""
    charts = []
    if dates and numeric:
        date_col, value_col = dates[0], numeric[0]
        frame = data[[date_col, value_col]].copy()
        frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce")
        frame = frame.dropna().sort_values(date_col)
        charts.append(px.line(frame, x=date_col, y=value_col, markers=True, title=f"Trend of {value_col}"))
    elif numeric:
        charts.append(px.histogram(data, x=numeric[0], nbins=24, title=f"Distribution of {numeric[0]}"))
    else:
        counts = data[categorical[0]].fillna("Missing").astype(str).value_counts().head(15) if categorical else pd.Series([len(data)], index=["Rows"])
        charts.append(px.bar(counts.sort_values(), orientation="h", title="Most common segments"))

    if categorical and numeric:
        group = data.assign(_group=data[categorical[0]].fillna("Missing").astype(str)).groupby("_group", as_index=False)[numeric[0]].mean().sort_values(numeric[0]).tail(12)
        charts.append(px.bar(group, x=numeric[0], y="_group", orientation="h", title=f"Average {numeric[0]} by {categorical[0]}"))
    elif len(numeric) >= 2:
        charts.append(px.scatter(data, x=numeric[0], y=numeric[1], title=f"Relationship: {numeric[0]} vs {numeric[1]}"))
    else:
        charts.append(px.bar(data.head(15), title="Uploaded records (preview)"))

    if len(numeric) >= 2:
        corr = data[numeric].corr(numeric_only=True).round(2)
        charts.append(px.imshow(corr, text_auto=True, color_continuous_scale="RdBu_r", zmin=-1, zmax=1, title="Signals moving together"))
    elif categorical:
        counts = data[categorical[-1]].fillna("Missing").astype(str).value_counts().head(12).sort_values()
        charts.append(px.bar(counts, orientation="h", title=f"Composition of {categorical[-1]}"))
    else:
        charts.append(px.histogram(data, x=numeric[0] if numeric else data.columns[0], title="Record profile"))

    if dates and categorical:
        date_col, group_col = dates[0], categorical[0]
        frame = data[[date_col, group_col]].copy()
        frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce")
        frame = frame.dropna()
        trend = frame.assign(Period=frame[date_col].dt.to_period("M").astype(str)).groupby(["Period", group_col], as_index=False).size()
        charts.append(px.area(trend, x="Period", y="size", color=group_col, title=f"{group_col} mix over time"))
    elif categorical:
        counts = data[categorical[0]].fillna("Missing").astype(str).value_counts().head(12).sort_values()
        charts.append(px.bar(counts, orientation="h", title=f"Top {categorical[0]} values"))
    else:
        charts.append(px.box(data, y=numeric[0] if numeric else data.columns[0], title="Range and outliers"))
    return charts[:4]


def insight_text(data, numeric, dates, categorical, missing_rate):
    parts = []
    if numeric:
        column = numeric[0]
        values = pd.to_numeric(data[column], errors="coerce").dropna()
        if len(values) > 2:
            parts.append(f"**{column}** spans {values.min():,.2f}–{values.max():,.2f}; the highest 10% of records average {values.quantile(.9):,.2f}, which may identify a concentrated priority segment.")
    if categorical:
        column = categorical[0]
        share = data[column].fillna("Missing").astype(str).value_counts(normalize=True).iloc[0] * 100
        parts.append(f"The largest **{column}** segment represents {share:.1f}% of records—check whether that concentration reflects demand, coverage, or a reporting bias.")
    if dates:
        parts.append(f"A time field (**{dates[0]}**) was detected, so the trend view can expose changes that a static summary would hide.")
    if not parts:
        parts.append("The file is too sparse for a strong directional finding yet; add more rows or descriptive fields to unlock comparisons.")
    quality = "Data looks sound for exploratory analysis." if missing_rate < .05 else "Some cleaning is recommended before decisions: missing values or inconsistent fields may affect comparisons."
    return quality, " ".join(parts)


with st.sidebar:
    st.header("Upload your data")
    uploads = st.file_uploader("Add one or more datasets", type=SUPPORTED_TYPES, accept_multiple_files=True, help="CSV, Excel, and JSON files are supported. Files are combined for analysis.")
    st.caption("Your files are analyzed in this session and are not written back to the repository.")

uploaded_data, errors = load_uploads(uploads)
using_demo = uploaded_data.empty
analysis_data = demo_data() if using_demo else uploaded_data
numeric, dates, categorical = profile(analysis_data)
missing_rate = float(analysis_data.isna().mean().mean()) if not analysis_data.empty else 0

st.title("⚓ Strategic Insight Studio")
st.caption("Upload almost any tabular dataset and receive four adaptive views designed to surface operational signals.")
if using_demo:
    st.info("Preview mode: this is an illustrative dataset. Upload one or more files to generate insights from your data.")
else:
    st.success(f"Analyzing {len(uploads)} file(s), {len(analysis_data):,} rows, and {len(analysis_data.columns):,} fields.")
for error in errors:
    st.warning(error)

metrics = st.columns(4)
metrics[0].metric("RECORDS", f"{len(analysis_data):,}")
metrics[1].metric("FIELDS", f"{len(analysis_data.columns):,}")
metrics[2].metric("NUMERIC SIGNALS", len(numeric))
metrics[3].metric("MISSING VALUES", f"{missing_rate:.1%}")

quality, strategic = insight_text(analysis_data, numeric, dates, categorical, missing_rate)
st.markdown(f'<div class="insight"><strong>{quality}</strong><br>{strategic}</div>', unsafe_allow_html=True)
st.divider()

st.subheader("Four most relevant views")
charts = chart_frame(analysis_data, numeric, dates, categorical)
for row_start in range(0, 4, 2):
    left, right = st.columns(2)
    for column, chart in zip((left, right), charts[row_start:row_start + 2]):
        chart.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=20, r=20, t=55, b=20))
        column.plotly_chart(chart, use_container_width=True)

with st.expander("Review prepared data"):
    st.caption("The table below is the combined analysis view. Use it to verify that your files were interpreted as expected.")
    st.dataframe(analysis_data.head(500), use_container_width=True, hide_index=True)
    st.download_button("Download combined view", analysis_data.to_csv(index=False).encode("utf-8"), "strategic_analysis_data.csv", "text/csv")

if not using_demo:
    st.caption("Tip: Start with the highest or lowest groups in the charts, then filter the source data to validate the story before acting.")
