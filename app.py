from io import BytesIO
from pathlib import Path
import re

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

SUPPORTED_TYPES = ["csv", "xlsx", "xls", "json", "parquet", "xml"]
DATE_WORDS = ("date", "dt", "day", "time", "start", "end", "arrival", "departure", "request", "created", "received", "distributed")
SENSITIVE_WORDS = r"name|employee|person|lname|fname|first.?name|last.?name|civmar.?/per"


def demo_data():
    rng = np.random.default_rng(7)
    dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=180, freq="D")
    workload = rng.normal(72, 18, 180).clip(10, 140).round(1)
    staffing = (workload * rng.normal(.91, .12, 180)).clip(5, 150).round(1)
    return pd.DataFrame({
        "Date": dates, "Region": rng.choice(["North", "South", "East", "West"], 180),
        "Workload": workload, "Staffing": staffing,
        "Readiness": (100 - (workload - staffing).clip(0) * 1.7).clip(35, 100).round(1),
        "Priority": rng.choice(["Routine", "Elevated", "Critical"], 180, p=[.55, .3, .15]),
    })


@st.cache_data(show_spinner=False)
def read_upload(file_name, file_bytes):
    suffix = Path(file_name).suffix.lower()
    stream = BytesIO(file_bytes)
    if suffix == ".csv":
        for encoding in ("utf-8-sig", "cp1252", "latin1"):
            try:
                stream.seek(0)
                return pd.read_csv(stream, encoding=encoding)
            except UnicodeDecodeError:
                continue
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(stream)
    if suffix == ".json":
        return pd.read_json(stream)
    if suffix == ".parquet":
        return pd.read_parquet(stream)
    if suffix == ".xml":
        return pd.read_xml(stream)
    raise ValueError(f"Unsupported file type: {suffix}")


def load_uploads(files):
    frames, errors = [], []
    for uploaded in files or []:
        try:
            frame = read_upload(uploaded.name, uploaded.getvalue()).copy()
            frame.columns = [str(c).strip() or f"Column {i + 1}" for i, c in enumerate(frame.columns)]
            frame = frame.dropna(how="all").reset_index(drop=True)
            frame["Source file"] = uploaded.name
            frames.append(frame)
        except Exception as exc:
            errors.append(f"{uploaded.name}: {exc}")
    return (pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()), errors


def parse_dates(series, column_name=""):
    clean = series.replace({"": np.nan, "#REF!": np.nan, "STAND BY": np.nan})
    # `infer_datetime_format` was deprecated in pandas 2 and removed in newer
    # pandas releases. Date inference is now the default behavior.
    parsed = pd.to_datetime(clean, errors="coerce")
    # Excel serial dates sometimes arrive as numbers in CSV exports.
    if parsed.notna().mean() < .7 and pd.api.types.is_numeric_dtype(clean):
        numeric = pd.to_numeric(clean, errors="coerce")
        excel_dates = pd.to_datetime(numeric, unit="D", origin="1899-12-30", errors="coerce")
        if excel_dates.notna().mean() > parsed.notna().mean():
            parsed = excel_dates
    return parsed


def profile(data):
    numeric, dates, categorical, text = [], [], [], []
    for column in data.columns:
        if column == "Source file":
            continue
        series = data[column]
        non_null = series.dropna()
        if not len(non_null):
            categorical.append(column)
            continue
        numeric_candidate = pd.to_numeric(non_null.astype(str).str.replace(",", "", regex=False), errors="coerce")
        date_candidate = parse_dates(series, column)
        name = str(column).lower()
        date_likely = any(word in name for word in DATE_WORDS) and date_candidate.notna().mean() >= .35
        if date_likely or (date_candidate.notna().mean() >= .85 and numeric_candidate.notna().mean() < .85 and non_null.nunique() > 1):
            dates.append(column)
        elif pd.api.types.is_numeric_dtype(series) or numeric_candidate.notna().mean() >= .9:
            numeric.append(column)
        elif non_null.nunique() <= min(30, max(10, len(data) * .2)):
            categorical.append(column)
        else:
            text.append(column)
    return numeric, dates, categorical, text


def clean_label(series):
    return series.fillna("Missing").astype(str).str.strip().replace({"": "Missing"})


def best_category(data, categorical):
    usable = [c for c in categorical if 2 <= data[c].nunique(dropna=True) <= min(30, max(5, len(data) // 2))]
    preferred = ("status", "location", "ship", "vessel", "arrival", "departure", "employee", "type", "travel writer")
    return sorted(usable, key=lambda c: (not any(k in c.lower() for k in preferred), data[c].nunique()))[0] if usable else (categorical[0] if categorical else None)


def charts_for(data, numeric, dates, categorical):
    charts = []
    category = best_category(data, categorical)
    # 1: composition/status is more useful than a generic first-column chart.
    if category:
        counts = clean_label(data[category]).value_counts().head(15).sort_values()
        charts.append((px.bar(counts, x=counts.values, y=counts.index, orientation="h", title=f"Composition by {category}"), f"Largest segments in {category}"))
    elif numeric:
        charts.append((px.histogram(data, x=numeric[0], nbins=24, title=f"Distribution of {numeric[0]}"), f"Distribution of {numeric[0]}"))
    else:
        charts.append((px.bar(x=["Rows"], y=[len(data)], title="Record count"), "Record count"))

    # 2: all date fields are stacked into a milestone/event timeline.
    if dates:
        events = []
        for col in dates[:8]:
            parsed = parse_dates(data[col], col)
            events.append(pd.DataFrame({"Date": parsed, "Event": col}))
        event_frame = pd.concat(events, ignore_index=True).dropna()
        if not event_frame.empty:
            by_day = event_frame.groupby(["Date", "Event"]).size().reset_index(name="Records")
            charts.append((px.line(by_day, x="Date", y="Records", color="Event", markers=True, title="Milestones and events over time"), "Date fields detected; timeline shows operational flow."))
        else:
            charts.append((px.bar(x=["No valid dates"], y=[0], title="Timeline unavailable"), "Date columns were detected but could not be parsed."))
    elif len(numeric) >= 2:
        charts.append((px.scatter(data, x=numeric[0], y=numeric[1], title=f"Relationship: {numeric[0]} vs {numeric[1]}"), "Numeric relationship"))
    else:
        charts.append((px.bar(x=["No time field"], y=[len(data)], title="No time field detected"), "Add a date field for trend analysis."))

    # 3: compare the most useful segment against a numeric signal, if available.
    if category and numeric:
        metric = numeric[0]
        grouped = data.assign(_category=clean_label(data[category]), _metric=pd.to_numeric(data[metric], errors="coerce"))
        grouped = grouped.groupby("_category", as_index=False)['_metric'].agg(['mean', 'count']).reset_index().sort_values('mean').tail(15)
        charts.append((px.bar(grouped, x="mean", y="_category", orientation="h", text="count", title=f"Average {metric} by {category}"), f"Comparison of {metric} across {category}"))
    elif len(numeric) >= 2:
        corr = data[numeric].corr(numeric_only=True).round(2)
        charts.append((px.imshow(corr, text_auto=True, color_continuous_scale="RdBu_r", zmin=-1, zmax=1, title="Numeric signals moving together"), "Correlation view"))
    else:
        missing = data.isna().mean().sort_values().tail(12).sort_values()
        charts.append((px.bar(x=missing.values, y=missing.index, orientation="h", title="Missingness by field"), "Data completeness"))

    # 4 is deliberately always data quality: it prevents overconfident analysis.
    missing = data.isna().mean().sort_values().tail(15).sort_values()
    charts.append((px.bar(x=missing.values, y=missing.index, orientation="h", range_x=[0, 1], title="Data quality: missing values by field"), "Prioritize fields with high missingness before acting."))
    return charts[:4]


def insights(data, numeric, dates, categorical, text):
    findings = []
    if categorical:
        category = best_category(data, categorical)
        counts = clean_label(data[category]).value_counts()
        if len(counts):
            findings.append(f"**{counts.index[0]}** is the largest `{category}` segment at **{counts.iloc[0] / len(data):.1%}** of records.")
    if dates:
        date_col = dates[0]
        parsed = parse_dates(data[date_col], date_col).dropna()
        if len(parsed):
            findings.append(f"`{date_col}` spans **{parsed.min():%Y-%m-%d} to {parsed.max():%Y-%m-%d}**; use the timeline to validate sequencing and bottlenecks.")
    missing = data.isna().mean().sort_values(ascending=False)
    if len(missing) and missing.iloc[0] >= .25:
        findings.append(f"Data-quality risk: **{missing.index[0]}** is missing in **{missing.iloc[0]:.1%}** of rows.")
    if text:
        keyword_hits = data[text].fillna("").astype(str).apply(lambda s: s.str.contains(r"unable|await|stand.?by|delay|cancel|no.?show|ref", case=False, regex=True).sum()).sum()
        if keyword_hits:
            findings.append(f"The free-text fields contain **{int(keyword_hits)}** operational exception markers; review the attention queue below.")
    return " ".join(findings) or "Not enough structure for a directional finding; validate the source schema first."


def sensitive_columns(frame):
    """Return columns whose names suggest they may contain personal identifiers."""
    return [column for column in frame.columns if re.search(SENSITIVE_WORDS, str(column), re.I)]


def mask_sensitive(frame, columns=None):
    result = frame.copy()
    columns = sensitive_columns(result) if columns is None else columns
    for column in columns:
        result[column] = result[column].notna().map({True: "[present]", False: "[missing]"})
    return result


with st.sidebar:
    st.header("Upload your data")
    uploads = st.file_uploader("Add one or more datasets", type=SUPPORTED_TYPES, accept_multiple_files=True)
    st.caption("Supported: CSV, Excel, JSON, Parquet, XML. Files are analyzed in-session.")

uploaded_data, errors = load_uploads(uploads)
using_demo = uploaded_data.empty
analysis_data = demo_data() if using_demo else uploaded_data

# Scan the schema first, then let the user decide how identifier-like fields are shown.
detected_sensitive = [] if using_demo else sensitive_columns(analysis_data)
mask_names = True
if detected_sensitive:
    st.warning(
        "Potential personal identifiers were detected in the uploaded schema. "
        "Masking is recommended before displaying previews or downloading prepared data. "
        "The choice below only controls display/export masking; the uploaded values remain in-session for analysis."
    )
    st.write("Detected fields: " + ", ".join(f"`{column}`" for column in detected_sensitive))
    masking_choice = st.radio(
        "How should these fields be handled in previews and downloads?",
        ("Mask detected fields (recommended)", "Continue without masking"),
        index=0,
        key="sensitive_data_choice",
    )
    mask_names = masking_choice.startswith("Mask")
    if not mask_names:
        st.info("You chose to continue without masking. Make sure you are authorized to view and export these identifiers.")

numeric, dates, categorical, text = profile(analysis_data)

# Add focused filters rather than forcing the user to understand the schema.
with st.sidebar:
    filter_columns = [c for c in categorical if 1 < analysis_data[c].nunique(dropna=True) <= 20][:4]
    selected = {}
    for column in filter_columns:
        values = sorted(clean_label(analysis_data[column]).unique().tolist())
        selected[column] = st.multiselect(column, values, default=values)

filtered = analysis_data.copy()
for column, values in selected.items():
    if values:
        filtered = filtered[clean_label(filtered[column]).isin(values)]

missing_rate = float(filtered.isna().mean().mean()) if not filtered.empty else 0
st.title("⚓ Strategic Insight Studio")
st.caption("Upload a tabular dataset. The app profiles it, filters it, identifies operational risk, and selects four decision-useful views.")
if using_demo:
    st.info("Preview mode: upload your file to replace the illustrative data.")
else:
    st.success(f"Analyzing {len(uploads)} file(s), {len(filtered):,} filtered rows, and {len(filtered.columns):,} fields.")
for error in errors:
    st.warning(error)

metrics = st.columns(4)
metrics[0].metric("RECORDS", f"{len(filtered):,}")
metrics[1].metric("FIELDS", f"{len(filtered.columns):,}")
metrics[2].metric("DATE / NUMERIC SIGNALS", f"{len(dates)} / {len(numeric)}")
metrics[3].metric("MISSING VALUES", f"{missing_rate:.1%}")

quality = "Data looks sound for exploration." if missing_rate < .05 else "Proceed carefully: missingness or malformed values can distort conclusions."
st.markdown(f'<div class="insight"><strong>{quality}</strong><br>{insights(filtered, numeric, dates, categorical, text)}</div>', unsafe_allow_html=True)

st.subheader("Four most relevant views")
for row_start in range(0, 4, 2):
    left, right = st.columns(2)
    for column, (chart, explanation) in zip((left, right), charts_for(filtered, numeric, dates, categorical)[row_start:row_start + 2]):
        chart.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=20, r=20, t=55, b=20))
        column.plotly_chart(chart, use_container_width=True)
        column.caption(explanation)

# A practical attention queue for incomplete/exception-heavy operational rows.
with st.expander("Attention queue and prepared data"):
    exception_columns = [c for c in text if c != "Source file"]
    if exception_columns:
        exception_mask = filtered[exception_columns].fillna("").astype(str).apply(lambda col: col.str.contains(r"unable|await|stand.?by|delay|cancel|no.?show|#REF!", case=False, regex=True)).any(axis=1)
        queue = filtered.loc[exception_mask].copy()
        st.write(f"**{len(queue):,}** rows contain an exception marker in free text or formula errors.")
        queue_preview = mask_sensitive(queue.head(200), detected_sensitive) if mask_names else queue.head(200)
        st.dataframe(queue_preview, use_container_width=True, hide_index=True)
    else:
        st.caption("No free-text exception field was detected.")
    prepared = mask_sensitive(filtered, detected_sensitive) if mask_names else filtered
    st.dataframe(prepared.head(500), use_container_width=True, hide_index=True)
    st.download_button("Download prepared view", prepared.to_csv(index=False).encode("utf-8"), "strategic_analysis_data.csv", "text/csv")

if not using_demo:
    st.caption("No-BS rule: charts identify patterns; verify the underlying records before making an operational decision.")
