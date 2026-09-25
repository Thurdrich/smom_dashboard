from io import BytesIO
from pathlib import Path
import re

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="SMOM | Strategic Insight Studio", page_icon="⚓", layout="wide")

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
SENSITIVE_NAME_WORDS = ("address", "street", "phone", "mobile", "telephone", "email", "e-mail", "ssn", "social security", "employee id", "employee number", "personnel id", "personnel number", "badge", "passport", "account", "routing")
NAME_WORDS = ("name", "first", "last", "employee", "person", "contact")


def demo_data():
    rng = np.random.default_rng(7)
    dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=180, freq="D")
    workload = rng.normal(72, 18, 180).clip(10, 140).round(1)
    staffing = (workload * rng.normal(.91, .12, 180)).clip(5, 150).round(1)
    return pd.DataFrame({"Date": dates, "Region": rng.choice(["North", "South", "East", "West"], 180), "Workload": workload, "Staffing": staffing, "Readiness": (100 - (workload - staffing).clip(0) * 1.7).clip(35, 100).round(1), "Priority": rng.choice(["Routine", "Elevated", "Critical"], 180, p=[.55, .3, .15])})


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


def parse_dates(series):
    clean = series.replace({"": np.nan, "#REF!": np.nan, "STAND BY": np.nan})
    parsed = pd.to_datetime(clean, errors="coerce")
    if parsed.notna().mean() < .7 and pd.api.types.is_numeric_dtype(clean):
        excel_dates = pd.to_datetime(pd.to_numeric(clean, errors="coerce"), unit="D", origin="1899-12-30", errors="coerce")
        if excel_dates.notna().mean() > parsed.notna().mean():
            parsed = excel_dates
    return parsed


def clean_label(series):
    return series.fillna("Missing").astype(str).str.strip().replace({"": "Missing"})


def detect_sensitive(data):
    """Conservative detection: protect direct identifiers, but leave names owner-controlled."""
    detected, reasons, names = [], {}, []
    for column in data.columns:
        if column == "Source file":
            continue
        label = str(column).lower()
        sample = data[column].dropna().astype(str).head(500)
        reason = []
        if any(word in label for word in SENSITIVE_NAME_WORDS):
            reason.append("sensitive column name")
        if len(sample):
            phone_hits = sample.str.contains(r"(?:\+?\d[\d .()\-]{7,}\d)", regex=True).mean()
            email_hits = sample.str.contains(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", regex=True).mean()
            id_hits = sample.str.contains(r"^(?:[A-Z]{0,4}[- ]?\d{5,}|\d{6,})$", regex=True).mean()
            if phone_hits >= .15:
                reason.append("phone-like values")
            if email_hits >= .15:
                reason.append("email-like values")
            if id_hits >= .15:
                reason.append("identifier-like values")
        if reason:
            detected.append(column)
            reasons[column] = ", ".join(reason)
        elif any(word in label for word in NAME_WORDS):
            names.append(column)
    return detected, reasons, names


def profile(data):
    numeric, dates, categorical, text = [], [], [], []
    for column in data.columns:
        if column == "Source file":
            continue
        series, non_null = data[column], data[column].dropna()
        if not len(non_null):
            categorical.append(column)
            continue
        numeric_candidate = pd.to_numeric(non_null.astype(str).str.replace(",", "", regex=False), errors="coerce")
        date_candidate = parse_dates(series)
        label = str(column).lower()
        date_likely = any(word in label for word in DATE_WORDS) and date_candidate.notna().mean() >= .35
        if date_likely or (date_candidate.notna().mean() >= .85 and numeric_candidate.notna().mean() < .85 and non_null.nunique() > 1):
            dates.append(column)
        elif pd.api.types.is_numeric_dtype(series) or numeric_candidate.notna().mean() >= .9:
            numeric.append(column)
        elif non_null.nunique() <= min(30, max(10, len(data) * .2)):
            categorical.append(column)
        else:
            text.append(column)
    return numeric, dates, categorical, text


def best_category(data, categorical):
    usable = [c for c in categorical if 2 <= data[c].nunique(dropna=True) <= min(30, max(5, len(data) // 2))]
    return sorted(usable, key=lambda c: (data[c].nunique(), len(str(c))))[0] if usable else (categorical[0] if categorical else None)


def make_charts(data, numeric, dates, categorical):
    charts = []
    category = best_category(data, categorical)
    if category:
        counts = clean_label(data[category]).value_counts().head(15).sort_values()
        charts.append((px.bar(x=counts.values, y=counts.index, orientation="h", title=f"Composition by {category}"), "Largest segments."))
    elif numeric:
        charts.append((px.histogram(data, x=numeric[0], nbins=24, title=f"Distribution of {numeric[0]}"), "Distribution and concentration."))
    else:
        charts.append((px.bar(x=["Rows"], y=[len(data)], title="Record count"), "Record count."))

    if dates:
        event_frames = [pd.DataFrame({"Date": parse_dates(data[c]), "Event": c}) for c in dates[:8]]
        events = pd.concat(event_frames, ignore_index=True).dropna()
        timeline = events.groupby(["Date", "Event"]).size().reset_index(name="Records")
        charts.append((px.line(timeline, x="Date", y="Records", color="Event", markers=True, title="Detected milestones over time"), "Date sequencing and activity."))
    elif len(numeric) >= 2:
        charts.append((px.scatter(data, x=numeric[0], y=numeric[1], title=f"Relationship: {numeric[0]} vs {numeric[1]}"), "Potential relationship; correlation is not causation."))
    else:
        charts.append((px.bar(x=["No time field"], y=[len(data)], title="No time field detected"), "No defensible trend available."))

    if category and numeric:
        metric = numeric[0]
        grouped = data.assign(_category=clean_label(data[category]), _metric=pd.to_numeric(data[metric], errors="coerce")).groupby("_category", as_index=False)["_metric"].mean().sort_values("_metric").tail(15)
        charts.append((px.bar(grouped, x="_metric", y="_category", orientation="h", title=f"Average {metric} by {category}"), "Segment comparison."))
    elif len(numeric) >= 2:
        charts.append((px.imshow(data[numeric].corr().round(2), text_auto=True, color_continuous_scale="RdBu_r", zmin=-1, zmax=1, title="Numeric signals moving together"), "Relationship screening."))
    else:
        charts.append((px.bar(x=data.isna().mean().sort_values().tail(12).values, y=data.isna().mean().sort_values().tail(12).index, orientation="h", title="Missingness by field"), "Completeness gap."))

    missing = data.isna().mean().sort_values().tail(15).sort_values()
    charts.append((px.bar(x=missing.values, y=missing.index, orientation="h", range_x=[0, 1], title="Data quality: missing values"), "Use this to prioritize cleanup before decisions."))
    return charts[:4]


def findings(data, numeric, dates, categorical, text):
    items = []
    if categorical:
        category = best_category(data, categorical)
        counts = clean_label(data[category]).value_counts()
        if len(counts):
            items.append(f"**Observation:** `{counts.index[0]}` is the largest `{category}` segment at **{counts.iloc[0] / len(data):.1%}**.")
    missing = data.isna().mean().sort_values(ascending=False)
    if len(missing) and missing.iloc[0] >= .25:
        items.append(f"**Data-quality gap:** `{missing.index[0]}` is missing in **{missing.iloc[0]:.1%}** of records.")
    if dates:
        valid_dates = pd.concat([parse_dates(data[c]) for c in dates], ignore_index=True).dropna()
        if len(valid_dates):
            items.append(f"**Coverage:** detected date values span **{valid_dates.min():%Y-%m-%d} to {valid_dates.max():%Y-%m-%d}**.")
    if text:
        markers = data[text].fillna("").astype(str).apply(lambda col: col.str.contains(r"unable|await|stand.?by|delay|cancel|no.?show|#REF!", case=False, regex=True)).any(axis=1).sum()
        if markers:
            items.append(f"**Potential risk:** **{int(markers)}** records contain exception-like text or formula errors; review them before acting.")
    return " ".join(items) or "**Needs validation:** the available structure is insufficient for a directional finding."


def privacy_report(data, auto_sensitive, names, protected, show_names):
    omitted = [c for c in auto_sensitive if c in protected]
    visible_names = [c for c in names if c not in protected and show_names]
    return omitted, visible_names


with st.sidebar:
    st.header("Upload data")
    uploads = st.file_uploader("Add one or more datasets", type=SUPPORTED_TYPES, accept_multiple_files=True)
    st.divider()
    st.subheader("Privacy review")
    st.caption("Direct identifiers are protected before profiling. Names remain owner-controlled.")
    show_names = st.checkbox("Names may be visible in this session", value=True)

uploaded_data, errors = load_uploads(uploads)
using_demo = uploaded_data.empty
raw_data = demo_data() if using_demo else uploaded_data
auto_sensitive, sensitive_reasons, name_candidates = detect_sensitive(raw_data)

with st.sidebar:
    default_protected = auto_sensitive + ([] if show_names else name_candidates)
    protected = st.multiselect("Fields to omit from analysis and exports", list(raw_data.columns), default=default_protected, help="The data owner can add or remove fields before analysis. Direct identifiers detected by the app are selected by default.")
    if auto_sensitive:
        st.caption("Auto-protected: " + ", ".join(auto_sensitive))

# Privacy boundary: only this sanitized frame reaches profiling, charts, insights, and downloads.
analysis_data = raw_data.drop(columns=[c for c in protected if c in raw_data.columns], errors="ignore").copy()
numeric, dates, categorical, text = profile(analysis_data)
missing_rate = float(analysis_data.isna().mean().mean()) if not analysis_data.empty else 0

st.title("⚓ Strategic Insight Studio")
st.caption("Domain-neutral analysis with a visible privacy review before any chart or finding is produced.")
if using_demo:
    st.info("Preview mode: upload a dataset to replace the illustrative data.")
else:
    st.success(f"Analyzing {len(uploads)} file(s), {len(analysis_data):,} records, and {len(analysis_data.columns):,} approved fields.")
for error in errors:
    st.warning(error)

omitted, visible_names = privacy_report(raw_data, auto_sensitive, name_candidates, protected, show_names)
with st.expander("Privacy report", expanded=bool(omitted or name_candidates)):
    st.write(f"**Fields omitted before analysis:** {len(omitted)} | **Fields visible to analysis:** {len(analysis_data.columns)}")
    if omitted:
        st.warning("Omitted: " + ", ".join(omitted))
        st.caption("Detection reasons: " + "; ".join(f"{c} ({sensitive_reasons.get(c, 'owner-selected')})" for c in omitted))
    if name_candidates:
        st.info("Name-like fields are owner-controlled: " + ", ".join(name_candidates))
    if visible_names:
        st.caption("Names are visible because the data owner explicitly allowed them for this session: " + ", ".join(visible_names))
    st.caption("This is an application privacy boundary, not a substitute for deployment authentication, HTTPS, access control, or a managed secret store.")

metrics = st.columns(4)
metrics[0].metric("RECORDS", f"{len(analysis_data):,}")
metrics[1].metric("APPROVED FIELDS", f"{len(analysis_data.columns):,}")
metrics[2].metric("DATE / NUMERIC", f"{len(dates)} / {len(numeric)}")
metrics[3].metric("MISSING VALUES", f"{missing_rate:.1%}")
quality = "Data looks sound for exploration." if missing_rate < .05 else "Proceed carefully: missingness or malformed values can distort conclusions."
st.markdown(f'<div class="insight"><strong>{quality}</strong><br>{findings(analysis_data, numeric, dates, categorical, text)}</div>', unsafe_allow_html=True)

st.subheader("Four most relevant views")
charts = make_charts(analysis_data, numeric, dates, categorical)
for row_start in range(0, 4, 2):
    left, right = st.columns(2)
    for column, (chart, explanation) in zip((left, right), charts[row_start:row_start + 2]):
        chart.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=20, r=20, t=55, b=20))
        column.plotly_chart(chart, use_container_width=True)
        column.caption(explanation)

with st.expander("Review approved data and attention queue"):
    if text:
        exception_mask = analysis_data[text].fillna("").astype(str).apply(lambda col: col.str.contains(r"unable|await|stand.?by|delay|cancel|no.?show|#REF!", case=False, regex=True)).any(axis=1)
        st.write(f"**{int(exception_mask.sum()):,}** approved records contain exception-like text or formula errors.")
        st.dataframe(analysis_data.loc[exception_mask].head(200), use_container_width=True, hide_index=True)
    st.dataframe(analysis_data.head(500), use_container_width=True, hide_index=True)
    st.download_button("Download approved/sanitized view", analysis_data.to_csv(index=False).encode("utf-8"), "strategic_analysis_data.csv", "text/csv")

st.caption("No-BS rule: findings identify patterns and gaps; validate source records before making decisions.")
