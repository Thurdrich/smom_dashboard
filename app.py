import hashlib

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard import SUPPORTED_TYPES, chart_tables, default_field, load_uploads, local_answer


st.set_page_config(page_title="SMOM Travel Dashboard", layout="wide")
st.markdown(
    """<style>
    .stApp { background-color: #fff; color: #242424; }
    .block-container { max-width: 1800px; }
    h1 { text-align: center; }
    </style>""",
    unsafe_allow_html=True,
)

st.title("SMOM Travel Analysis Dashboard")

with st.sidebar:
    st.header("Upload travel data")
    uploads = st.file_uploader(
        "Upload one or more files", type=SUPPORTED_TYPES, accept_multiple_files=True
    )
    st.caption("Analysis and chat run locally; uploaded data is not sent to an AI service.")

data, errors = load_uploads(uploads)
for error in errors:
    st.error(error)
if data.empty:
    st.info("Upload travel data to display the four charts and ask questions.")
    st.stop()

columns = [c for c in data.columns if c != "Source file"]
options = [None, *columns]
defaults = {
    "status": ("status", "travel status"),
    "traveler": ("civmar/per", "traveler", "traveller", "traveler name", "name"),
    "vessel": ("vessel", "ship", "ship name"),
    "date": ("date 1", "expected date", "planned date", "travel date"),
    "location": ("location", "destination", "port"),
}
with st.sidebar:
    st.header("Chart fields")
    st.caption("Check the detected fields or select the appropriate columns.")
    fields = {}
    for key, label in [
        ("status", "Status"),
        ("traveler", "Traveler name or ID"),
        ("vessel", "Vessel"),
        ("date", "Expected movement date"),
        ("location", "Location"),
    ]:
        default = default_field(columns, defaults[key])
        fields[key] = st.selectbox(label, options, index=options.index(default), format_func=lambda x: x or "Not selected")

    st.header("Filters")
    filtered = data
    for key in ("status", "vessel", "location"):
        column = fields[key]
        if column:
            labels = filtered[column].fillna("").astype(str).str.strip().replace("", "Missing")
            choices = sorted(labels.unique())
            selected = st.multiselect(f"Filter by {key}", choices, key=f"filter_{key}")
            if selected:
                filtered = filtered.loc[labels.isin(selected)]

st.caption(f"{len(filtered):,} movement rows from {len(uploads):,} uploaded file(s).")
st.caption(
    "Status and date charts count rows. Vessel and location charts count distinct named travelers "
    "within each group; rows without a traveler name are excluded from those charts."
)
if filtered.empty:
    st.warning("No rows match the current filters.")

tables = chart_tables(filtered, fields)
specs = [
    ("status", "Movement Status", "Movement rows", px.colors.sequential.Viridis),
    ("vessel", "Travelers by Vessel", "Distinct travelers", px.colors.sequential.Plasma),
    ("date", "Expected Movements Over Time", "Movement rows", px.colors.sequential.Viridis),
    ("location", "Travelers by Location", "Distinct travelers", px.colors.sequential.Cividis),
]
for row_start in (0, 2):
    chart_columns = st.columns(2)
    for container, (key, title, y_label, colors) in zip(chart_columns, specs[row_start:row_start + 2]):
        with container:
            st.subheader(title)
            table = tables[key]
            if table is None:
                required = "a traveler and " if key in ("vessel", "location") else ""
                st.info(f"Select {required}a {key if key != 'date' else 'movement date'} field in the sidebar.")
            elif table.empty:
                st.info("No usable values are available for this chart.")
            else:
                if key == "date":
                    chart = px.bar(table, x="Date", y="Count", labels={"Count": y_label})
                    chart.update_traces(marker_color="#356b91")
                else:
                    chart = px.bar(table, x="Group", y="Count", color="Group",
                                   color_discrete_sequence=colors,
                                   labels={"Group": fields[key], "Count": y_label})
                    chart.update_layout(showlegend=False)
                chart.update_layout(template="plotly_white", height=440, margin=dict(t=20, b=30))
                chart.update_xaxes(showgrid=True, tickangle=-45)
                chart.update_yaxes(showgrid=True, rangemode="tozero")
                st.plotly_chart(chart, width="stretch", key=f"chart_{key}")
            if key == "date" and fields["date"]:
                st.caption(f"Baseline: {fields['date']}. Rows with missing or invalid dates are excluded.")

st.subheader("Ask about the data and charts")
st.caption("Local, rule-based answers use the current filters and chart fields. Ask about one chart at a time.")
fingerprint = hashlib.sha256(
    pd.util.hash_pandas_object(filtered, index=True).values.tobytes()
    + repr((tuple(filtered.columns), fields)).encode()
).hexdigest()
if st.session_state.get("chat_context") != fingerprint:
    st.session_state.chat_history = []
    st.session_state.chat_context = fingerprint
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
question = st.chat_input("Ask about status, vessels, movement dates, or locations")
if question:
    answer = local_answer(question, filtered, fields, tables)
    st.session_state.chat_history.extend([
        {"role": "user", "content": question},
        {"role": "assistant", "content": answer},
    ])
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        st.write(answer)
