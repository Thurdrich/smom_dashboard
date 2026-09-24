from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Epic Fury | Movement Command Center",
    page_icon="⚓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# The committed Excel workbook is the only permanent dashboard data source.
SOURCE_FILE = "MEFMT_data (1).xlsx"
STALE_AFTER_DAYS = 30
REQUIRED_COLUMNS = {"STATUS", "SEX", "CIVMAR/PER", "VESSEL", "LOCATION"}
DATE_COLUMNS = ["DATE_1", "DATE_2", "DOA", "DUE OFF DT", "LILP DATE"]
STATUS_COLORS = {
    "ON LOCATION": "#27ae60",
    "PENDING": "#f39c12",
    "TRAVEL CONFIRMED": "#2980b9",
    "CANCELLED": "#c0392b",
    "NO SHOW": "#8e44ad",
    "IN TRANSIT": "#00a6b2",
    "ARRIVAL PENDING": "#e67e22",
    "STANDBY": "#8e44ad",
}

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


def read_source(upload_bytes=None, upload_name=SOURCE_FILE):
    if upload_bytes is not None:
        stream = BytesIO(upload_bytes)
        if upload_name.lower().endswith((".xlsx", ".xls")):
            return pd.read_excel(stream), upload_name
        return pd.read_csv(stream), upload_name

    path = Path(__file__).resolve().parent / SOURCE_FILE
    if not path.exists() or path.stat().st_size <= 1:
        return None, SOURCE_FILE
    return pd.read_excel(path), SOURCE_FILE


def clean_and_validate(data):
    data = data.copy()
    data.columns = [str(column).strip() for column in data.columns]
    missing = REQUIRED_COLUMNS - set(data.columns)
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(sorted(missing)))

    data = data.rename(
        columns={
            "CIVMAR/PER": "PERSON",
            "EXT STATUS": "EXT_STATUS",
            "IN/OUT": "IN_OUT",
            "DATE 1": "DATE_1",
            "DATE 2": "DATE_2",
            "COMMENTS & ACTIONS": "COMMENTS",
        }
    )
    if data.empty:
        raise ValueError("The source contains no passenger rows.")

    data["PERSON"] = data["PERSON"].astype("string").str.strip()
    if data["PERSON"].isna().any() or data["PERSON"].eq("").any():
        raise ValueError("Every passenger row must contain a passenger name.")

    invalid_date_counts = {}
    for column in DATE_COLUMNS:
        if column in data:
            original = data[column].copy()
            parsed = pd.to_datetime(original, errors="coerce")
            invalid = original.notna() & original.astype(str).str.strip().ne("") & parsed.isna()
            if invalid.any():
                invalid_date_counts[column] = int(invalid.sum())
            data[column] = parsed

    for column in data.columns:
        if data[column].dtype == "object" or str(data[column].dtype) == "string":
            data[column] = (
                data[column]
                .replace(r"^\s*$", pd.NA, regex=True)
                .fillna("Unknown")
                .astype(str)
                .str.strip()
            )

    data["STATUS"] = data["STATUS"].str.upper()
    data.insert(0, "SOURCE_ROW", range(2, len(data) + 2))
    blank_cells = int((data == "Unknown").sum().sum())
    audit = {
        "passengers": len(data),
        "blank_cells": blank_cells,
        "invalid_dates": invalid_date_counts,
    }
    return data, audit


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


def text_col(data, column):
    if column in data:
        return data[column].fillna("Unknown").astype(str).str.upper()
    return pd.Series("Unknown", index=data.index)


def apply_filters(data):
    with st.sidebar:
        st.header("Mission filters")
        search = st.text_input("Search passengers", placeholder="Last name or full name")

        def choose(label, column):
            values = sorted(text_col(data, column).unique().tolist()) if column in data else []
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
    for column, value in [("STATUS", status), ("LOCATION", location), ("VESSEL", vessel), ("SEX", sex)]:
        if value != "ALL" and column in result:
            result = result[text_col(result, column) == value]
    return result


def answer_question(question, data):
    query = question.lower().strip()
    status = text_col(data, "STATUS")
    if any(word in query for word in ["how many", "count", "total"]):
        for key in sorted(status.unique(), key=len, reverse=True):
            if key.lower() in query:
                return f"There are **{int((status == key).sum())}** passengers with status **{key}** in the current filtered view."
        return f"The current filtered view contains **{len(data)}** passengers."
    if "status" in query or "breakdown" in query:
        return "Status breakdown: " + ", ".join(f"**{key}** ({value})" for key, value in status.value_counts().items())
    if "location" in query and "LOCATION" in data:
        values = text_col(data, "LOCATION").value_counts().head(8)
        return "Top locations: " + ", ".join(f"**{key}** ({value})" for key, value in values.items())
    if "vessel" in query and "VESSEL" in data:
        values = text_col(data, "VESSEL").value_counts().head(8)
        return "Top vessels: " + ", ".join(f"**{key}** ({value})" for key, value in values.items())
    if "PERSON" in data:
        matches = data[text_col(data, "PERSON").str.contains(query.upper(), na=False)]
        if len(matches):
            row = matches.iloc[0]
            return f"I found **{row['PERSON']}** — status: **{row.get('STATUS', 'Unknown')}**, location: **{row.get('LOCATION', 'Unknown')}**, vessel: **{row.get('VESSEL', 'Unknown')}**."
    return "I can answer questions using the current Epic Fury passenger data."


with st.sidebar:
    st.subheader("Data update")
    replacement = st.file_uploader(
        "Upload a replacement CSV/XLSX",
        type=["csv", "xlsx", "xls"],
        help="Validated for this session only. The committed master remains MEFMT_data (1).xlsx.",
    )
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
    st.error(f"The master source `{SOURCE_FILE}` is missing or empty.")
    st.stop()

st.title("⚓ Epic Fury Movement Command Center")
st.caption("Passenger movement, travel readiness, and operational accountability")
source_path = Path(__file__).resolve().parent / SOURCE_FILE
if source_name == SOURCE_FILE and source_path.exists():
    age_days = (datetime.now(timezone.utc).timestamp() - source_path.stat().st_mtime) / 86400
    if age_days > STALE_AFTER_DAYS:
        st.warning(f"Source data is approximately {age_days:.0f} days old. Upload or commit a newer approved file.")

with st.expander("Data quality and update instructions"):
    st.write(
        f"**Source:** `{source_name}`  |  **Passenger rows:** {audit['passengers']}  |  **Blank fields left as Unknown:** {audit['blank_cells']}"
    )
    if audit["invalid_dates"]:
        st.warning(
            "Invalid date values were left blank: "
            + ", ".join(f"{key} ({value})" for key, value in audit["invalid_dates"].items())
        )
    st.info(
        "The committed master data file is MEFMT_data (1).xlsx. Uploaded replacements are temporary for the current session only."
    )

filtered = apply_filters(df)
status = text_col(filtered, "STATUS")
counts = status.value_counts()
metrics = [
    ("TOTAL PASSENGERS", len(filtered)),
    ("ON LOCATION", counts.get("ON LOCATION", 0)),
    ("PENDING", counts.get("PENDING", 0)),
    ("TRAVEL CONFIRMED", counts.get("TRAVEL CONFIRMED", 0)),
    ("NO SHOW", counts.get("NO SHOW", 0)),
]
for column, (label, value) in zip(st.columns(len(metrics)), metrics):
    column.metric(label, int(value))

st.divider()
chart_left, chart_right = st.columns(2)
if len(filtered):
    status_df = status.value_counts().rename_axis("Status").reset_index(name="Count")
    figure = px.bar(
        status_df,
        x="Status",
        y="Count",
        color="Status",
        color_discrete_map=STATUS_COLORS,
        title="Movement status",
    )
    figure.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    chart_left.plotly_chart(figure, use_container_width=True)

    if "LOCATION" in filtered:
        locations = text_col(filtered, "LOCATION").value_counts().head(10).rename_axis("Location").reset_index(name="Count")
        location_figure = px.bar(
            locations,
            x="Count",
            y="Location",
            orientation="h",
            color="Count",
            color_continuous_scale="Blues",
            title="Top locations",
        )
        location_figure.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        chart_right.plotly_chart(location_figure, use_container_width=True)

st.divider()
tab_roster, tab_timeline, tab_chat = st.tabs(["📋 Roster", "🗓️ Travel timeline", "💬 Ask the tracker"])

with tab_roster:
    st.subheader("Passenger movement roster")
    preferred = [
        "SOURCE_ROW", "STATUS", "EXT_STATUS", "PERSON", "SEX", "RATING", "VESSEL",
        "LOCATION", "START", "IN_OUT", "DATE_1", "DATE_2", "DOA", "DUE OFF DT", "COMMENTS",
    ]
    view = filtered[[column for column in preferred if column in filtered] or list(filtered.columns)].copy()
    for column in view.columns:
        if pd.api.types.is_datetime64_any_dtype(view[column]):
            view[column] = view[column].dt.strftime("%Y-%m-%d")
    st.dataframe(view, use_container_width=True, hide_index=True)
    st.download_button(
        "Download filtered CSV",
        filtered.to_csv(index=False).encode("utf-8"),
        "epic_fury_filtered.csv",
        "text/csv",
    )

with tab_timeline:
    st.subheader("Upcoming / recorded travel dates")
    date_column = "DATE_1" if "DATE_1" in filtered else ("DATE_2" if "DATE_2" in filtered else None)
    if date_column and filtered[date_column].notna().any():
        timeline = filtered.dropna(subset=[date_column]).sort_values(date_column).copy()
        timeline["Person"] = timeline.get("PERSON", pd.Series("Passenger", index=timeline.index))
        timeline_figure = px.scatter(
            timeline,
            x=date_column,
            y="STATUS",
            color="STATUS",
            hover_name="Person",
            color_discrete_map=STATUS_COLORS,
            title="Movement activity by date",
        )
        timeline_figure.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(timeline_figure, use_container_width=True)
    else:
        st.info("No travel dates are available in the current filtered view.")

with tab_chat:
    st.subheader("Ask the Epic Fury tracker")
    st.caption("Answers use only the validated MEFMT master source.")
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    for role, message in st.session_state.chat_history:
        st.chat_message(role).markdown(message)
    prompt = st.chat_input("Ask: How many are pending? Where are passengers located?")
    if prompt:
        st.session_state.chat_history.extend(
            [("user", prompt), ("assistant", answer_question(prompt, filtered))]
        )
        st.rerun()
