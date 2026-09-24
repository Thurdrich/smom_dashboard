from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Epic Fury | Movement Command Center", page_icon="⚓", layout="wide", initial_sidebar_state="expanded")

SOURCE_FILE = "Epic Fury Data"
STALE_AFTER_DAYS = 30
REQUIRED_COLUMNS = {"STATUS", "SEX", "CIVMAR/PER", "VESSEL", "LOCATION"}
DATE_COLUMNS = ["DATE_1", "DATE_2", "DOA", "DUE OFF DT", "LILP DATE"]
STATUS_COLORS = {"ON LOCATION":"#27ae60", "PENDING":"#f39c12", "TRAVEL CONFIRMED":"#2980b9", "CANCELLED":"#c0392b", "NO SHOW":"#8e44ad", "IN TRANSIT":"#00a6b2", "ARRIVAL PENDING":"#e67e22", "STANDBY PASSENGER":"#7f8c8d"}

st.markdown("""
<style>
.stApp { background: radial-gradient(circle at top right,#123d61 0,#071a2f 42%,#061322 100%); color:#edf6ff; }
.block-container { max-width:1500px; padding-top:1.5rem; }
[data-testid="stSidebar"] { background:rgba(5,18,34,.96); border-right:1px solid rgba(255,255,255,.08); }
[data-testid="stMetric"] { background:linear-gradient(145deg,rgba(31,76,111,.72),rgba(10,32,55,.9)); border:1px solid rgba(115,192,224,.18); border-radius:14px; padding:14px; }
</style>
""", unsafe_allow_html=True)


def read_source(upload_bytes=None, upload_name=SOURCE_FILE):
    if upload_bytes is not None:
        stream = BytesIO(upload_bytes)
        if upload_name.lower().endswith((".xlsx", ".xls")):
            return pd.read_excel(stream), upload_name
        return pd.read_csv(stream), upload_name
    path = Path(__file__).resolve().parent / SOURCE_FILE
    if not path.exists() or path.stat().st_size <= 1:
        return None, SOURCE_FILE
    try:
        return pd.read_csv(path), SOURCE_FILE
    except (UnicodeDecodeError, pd.errors.ParserError):
        return pd.read_excel(path), SOURCE_FILE


def clean_and_validate(data):
    data = data.copy()
    data.columns = [str(c).strip() for c in data.columns]
    missing = REQUIRED_COLUMNS - set(data.columns)
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(sorted(missing)))
    data = data.rename(columns={"CIVMAR/PER":"PERSON", "EXT STATUS":"EXT_STATUS", "IN/OUT":"IN_OUT", "DATE 1":"DATE_1", "DATE 2":"DATE_2", "COMMENTS & ACTIONS":"COMMENTS"})
    if data.empty:
        raise ValueError("The source contains no passenger rows.")
    data["PERSON"] = data["PERSON"].astype("string").str.strip()
    if data["PERSON"].isna().any() or data["PERSON"].eq("").any():
        raise ValueError("Every passenger row must contain a passenger name.")
    invalid_date_counts = {}
    for col in DATE_COLUMNS:
        if col in data:
            original = data[col].copy()
            parsed = pd.to_datetime(original, errors="coerce")
            invalid = original.notna() & original.astype(str).str.strip().ne("") & parsed.isna()
            if invalid.any():
                invalid_date_counts[col] = int(invalid.sum())
            data[col] = parsed
    for col in data.columns:
        if data[col].dtype == "object" or str(data[col].dtype) == "string":
            data[col] = data[col].replace(r"^\s*$", pd.NA, regex=True).fillna("Unknown").astype(str).str.strip()
    data["STATUS"] = data["STATUS"].str.upper()
    data.insert(0, "SOURCE_ROW", range(2, len(data) + 2))
    blank_cells = int((data == "Unknown").sum().sum())
    return data, {"passengers": len(data), "blank_cells": blank_cells, "invalid_dates": invalid_date_counts}


@st.cache_data
def cached_load(upload_bytes=None, upload_name=SOURCE_FILE):
    raw, name = read_source(upload_bytes, upload_name)
    if raw is None:
        return None, name, None
    clean, audit = clean_and_validate(raw)
    return clean, name, audit


def load_data():
    upload = st.session_state.get("replacement_upload")
    if upload is not None:
        return cached_load(upload.getvalue(), upload.name)
    return cached_load()


def text_col(data, col):
    return data[col].fillna("Unknown").astype(str).str.upper() if col in data else pd.Series("Unknown", index=data.index)


def apply_filters(data):
    with st.sidebar:
        st.header("Mission filters")
        search = st.text_input("Search passengers", placeholder="Last name or full name")

        def choose(label, col):
            values = sorted(text_col(data, col).unique().tolist()) if col in data else []
            return st.selectbox(label, ["ALL"] + values)

        status = choose("Status", "STATUS")
        location = choose("Location", "LOCATION")
        vessel = choose("Vessel", "VESSEL")
        sex = choose("Sex", "SEX")
        st.divider()
        st.caption("All source passenger rows are included by default.")
    result = data.copy()
    if search and "PERSON" in result:
        result = result[text_col(result, "PERSON").str.contains(search.upper(), na=False)]
    for col, value in [("STATUS", status), ("LOCATION", location), ("VESSEL", vessel), ("SEX", sex)]:
        if value != "ALL" and col in result:
            result = result[text_col(result, col) == value]
    return result


def answer_question(question, data):
    q = question.lower().strip()
    status = text_col(data, "STATUS")
    if any(word in q for word in ["how many", "count", "total"]):
        for key in sorted(status.unique(), key=len, reverse=True):
            if key.lower() in q:
                return f"There are **{int((status == key).sum())}** passengers with status **{key}** in the current filtered view."
        return f"The current filtered view contains **{len(data)}** passengers."
    if "status" in q or "breakdown" in q:
        return "Status breakdown: " + ", ".join(f"**{k}** ({v})" for k, v in status.value_counts().items())
    if "location" in q and "LOCATION" in data:
        return "Top locations: " + ", ".join(f"**{k}** ({v})" for k, v in text_col(data, "LOCATION").value_counts().head(8).items())
    if "vessel" in q and "VESSEL" in data:
        return "Top vessels: " + ", ".join(f"**{k}** ({v})" for k, v in text_col(data, "VESSEL").value_counts().head(8).items())
    if "PERSON" in data:
        matches = data[text_col(data, "PERSON").str.contains(q.upper(), na=False)]
        if len(matches):
            row = matches.iloc[0]
            return f"I found **{row['PERSON']}** — status: **{row.get('STATUS', 'Unknown')}**, location: **{row.get('LOCATION', 'Unknown')}**, vessel: **{row.get('VESSEL', 'Unknown')}**."
    return "I can answer questions using the current Epic Fury passenger data."


with st.sidebar:
    st.subheader("Data update")
    replacement = st.file_uploader("Upload a replacement CSV/XLSX", type=["csv", "xlsx", "xls"], help="Validated for this session only. Commit the approved replacement as 'Epic Fury Data' to make it permanent.")
    if replacement is not None:
        st.session_state.replacement_upload = replacement
    if st.button("Clear uploaded replacement"):
        st.session_state.pop("replacement_upload", None)
        st.cache_data.clear()
        st.rerun()

try:
    df, source_name, audit = load_data()
except (ValueError, pd.errors.ParserError) as exc:
    st.error(f"Data validation failed: {exc}")
    st.stop()
if df is None:
    st.error(f"The sole dashboard source, `{SOURCE_FILE}`, is missing or empty.")
    st.stop()

st.title("⚓ Epic Fury Movement Command Center")
st.caption("Passenger movement, travel readiness, and operational accountability")
source_path = Path(__file__).resolve().parent / SOURCE_FILE
if source_name == SOURCE_FILE and source_path.exists():
    age_days = (datetime.now(timezone.utc).timestamp() - source_path.stat().st_mtime) / 86400
    if age_days > STALE_AFTER_DAYS:
        st.warning(f"Source data is approximately {age_days:.0f} days old. Upload or commit a newer approved file.")
with st.expander("Data quality and update instructions"):
    st.write(f"**Source:** `{source_name}`  |  **Passenger rows:** {audit['passengers']}  |  **Blank fields left as Unknown:** {audit['blank_cells']}")
    if audit["invalid_dates"]:
        st.warning("Invalid date values were left blank: " + ", ".join(f"{k} ({v})" for k, v in audit["invalid_dates"].items()))
    st.info("Strict mode does not interpolate dates, statuses, names, locations, or other passenger attributes across rows. Uploading a replacement here lasts only for this session. To make it permanent, replace the repository file named 'Epic Fury Data'.")

filtered = apply_filters(df)
status = text_col(filtered, "STATUS")
counts = status.value_counts()
metrics = [("TOTAL PASSENGERS", len(filtered)), ("ON LOCATION", counts.get("ON LOCATION", 0)), ("PENDING", counts.get("PENDING", 0)), ("TRAVEL CONFIRMED", counts.get("TRAVEL CONFIRMED", 0)), ("NO SHOW", counts.get("NO SHOW", 0)), ("CANCELLED", counts.get("CANCELLED", 0))]
for col, (label, value) in zip(st.columns(len(metrics)), metrics):
    col.metric(label, int(value))

st.divider()
chart_left, chart_right = st.columns(2)
if len(filtered):
    status_df = status.value_counts().rename_axis("Status").reset_index(name="Count")
    fig = px.bar(status_df, x="Status", y="Count", color="Status", color_discrete_map=STATUS_COLORS, title="Movement status")
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False)
    chart_left.plotly_chart(fig, use_container_width=True)
    if "LOCATION" in filtered:
        loc = text_col(filtered, "LOCATION").value_counts().head(10).rename_axis("Location").reset_index(name="Count")
        fig2 = px.bar(loc, x="Count", y="Location", orientation="h", color="Count", color_continuous_scale="Blues", title="Top locations")
        fig2.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        chart_right.plotly_chart(fig2, use_container_width=True)

st.divider()
tab_roster, tab_timeline, tab_chat = st.tabs(["📋 Roster", "🗓️ Travel timeline", "💬 Ask the tracker"])
with tab_roster:
    st.subheader("Passenger movement roster")
    preferred = ["SOURCE_ROW", "STATUS", "EXT_STATUS", "PERSON", "SEX", "RATING", "VESSEL", "LOCATION", "START", "IN_OUT", "DATE_1", "DATE_2", "DOA", "DUE OFF DT", "COMMENTS"]
    view = filtered[[c for c in preferred if c in filtered] or list(filtered.columns)].copy()
    for col in view.columns:
        if pd.api.types.is_datetime64_any_dtype(view[col]):
            view[col] = view[col].dt.strftime("%Y-%m-%d")
    st.dataframe(view, use_container_width=True, hide_index=True)
    st.download_button("Download filtered CSV", filtered.to_csv(index=False).encode("utf-8"), "epic_fury_filtered.csv", "text/csv")
with tab_timeline:
    st.subheader("Upcoming / recorded travel dates")
    date_col = "DATE_1" if "DATE_1" in filtered else ("DATE_2" if "DATE_2" in filtered else None)
    if date_col and filtered[date_col].notna().any():
        timeline = filtered.dropna(subset=[date_col]).sort_values(date_col).copy()
        timeline["Person"] = timeline.get("PERSON", pd.Series("Passenger", index=timeline.index))
        fig = px.scatter(timeline, x=date_col, y="STATUS", color="STATUS", hover_name="Person", color_discrete_map=STATUS_COLORS, title="Movement activity by date")
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No travel dates are available in the current filtered view.")
with tab_chat:
    st.subheader("Ask the Epic Fury tracker")
    st.caption("Answers use only the validated Epic Fury source.")
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    for role, message in st.session_state.chat_history:
        st.chat_message(role).markdown(message)
    prompt = st.chat_input("Ask: How many are pending? Where are passengers located?")
    if prompt:
        st.session_state.chat_history.extend([("user", prompt), ("assistant", answer_question(prompt, filtered))])
        st.rerun()
