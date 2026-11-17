import hashlib

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard import (
    SUPPORTED_TYPES,
    chart_tables,
    civmar_metrics,
    default_field,
    grouped_traveler_counts,
    load_uploads,
    local_answer,
    parse_movement_dates,
)


st.set_page_config(page_title="SMOM Travel Dashboard", layout="wide")
st.markdown(
    """<style>
    .stApp { background-color: #f7f6f2; color: #242424; }
    .block-container { max-width: 1800px; padding-top: 1.5rem; }
    h1 { text-align: center; }
    </style>""",
    unsafe_allow_html=True,
)


def _show_empty_data():
    if data.empty:
        st.info("Upload travel data in the sidebar to display this dashboard.")
        return True
    if filtered.empty:
        st.warning("No rows match the current filters.")
        return True
    return False


def _count_table(group_columns):
    return grouped_traveler_counts(filtered, group_columns, fields["traveler"])


def _render_overview():
    st.title("Operation Epic Fury CIVMAR Tracker")
    if _show_empty_data():
        return

    metrics = civmar_metrics(filtered, fields)
    metric_columns = st.columns(6)
    for column, label, value in zip(
        metric_columns,
        (
            "Total Travelers",
            "Pending Travel",
            "In Transit",
            "Arrived/On Location",
            "Requires Lodging",
            "Cancellation %",
        ),
        (
            f"{metrics['total']:,}",
            f"{metrics['pending']:,}",
            f"{metrics['in_transit']:,}",
            f"{metrics['arrived_on_location']:,}",
            f"{metrics['lodging']:,}",
            f"{metrics['cancellation_rate']:.2f}%",
        ),
    ):
        column.metric(label, value)

    vessel_column = fields["vessel"]
    direction_column = fields["direction"]
    status_column = fields["status"]
    rating_column = fields["rating"]
    left, right = st.columns([1.35, 1])
    with left:
        st.subheader("Travelers by Vessel and Direction")
        vessel_groups = [column for column in (vessel_column, direction_column) if column]
        vessel_counts = _count_table(vessel_groups)
        if not vessel_column or vessel_counts is None:
            st.info("Select a vessel field in the sidebar to show this chart.")
        elif vessel_counts.empty:
            st.info("No named travelers are available for this chart.")
        else:
            vessel_counts = vessel_counts.rename(columns={vessel_column: "Vessel"})
            if direction_column:
                vessel_counts = vessel_counts.rename(columns={direction_column: "Direction"})
                chart = px.bar(
                    vessel_counts,
                    x="Count",
                    y="Vessel",
                    color="Direction",
                    barmode="stack",
                    orientation="h",
                    color_discrete_sequence=["#073b70", "#c5a500", "#b6243d"],
                    labels={"Count": "Travelers"},
                )
            else:
                chart = px.bar(
                    vessel_counts,
                    x="Count",
                    y="Vessel",
                    orientation="h",
                    color_discrete_sequence=["#073b70"],
                    labels={"Count": "Travelers"},
                )
            chart.update_layout(template="plotly_white", height=470, margin=dict(t=10, b=20))
            chart.update_yaxes(categoryorder="total ascending")
            st.plotly_chart(chart, width="stretch", key="overview_vessel")

    with right:
        st.subheader("Travelers by Status")
        status_counts = _count_table([status_column] if status_column else [])
        if not status_column or status_counts is None:
            st.info("Select a status field in the sidebar to show this chart.")
        elif status_counts.empty:
            st.info("No named travelers are available for this chart.")
        else:
            status_counts = status_counts.rename(columns={status_column: "Status"})
            chart = px.treemap(
                status_counts,
                path=["Status"],
                values="Count",
                color="Status",
                color_discrete_sequence=[
                    "#073b70",
                    "#b6243d",
                    "#07569a",
                    "#c5a500",
                    "#8c8c8c",
                ],
            )
            chart.update_layout(template="plotly_white", height=260, margin=dict(t=8, b=8))
            st.plotly_chart(chart, width="stretch", key="overview_status")
        st.page_link(status_page, label="Open CIVMAR tracker by status")

        st.subheader("Top 10 Ratings by Travel Volume")
        rating_groups = [column for column in (rating_column, direction_column) if column]
        rating_counts = _count_table(rating_groups)
        if not rating_column or rating_counts is None:
            st.info("Select a rating field in the sidebar to show this chart.")
        elif rating_counts.empty:
            st.info("No named travelers are available for this chart.")
        else:
            rating_totals = rating_counts.groupby(rating_column)["Count"].sum()
            top_ratings = rating_totals.nlargest(10).index
            rating_counts = rating_counts[rating_counts[rating_column].isin(top_ratings)]
            rating_counts = rating_counts.rename(columns={rating_column: "Rating"})
            if direction_column:
                rating_counts = rating_counts.rename(columns={direction_column: "Direction"})
                chart = px.bar(
                    rating_counts,
                    x="Rating",
                    y="Count",
                    color="Direction",
                    barmode="group",
                    color_discrete_sequence=["#073b70", "#c5a500", "#b6243d"],
                    labels={"Count": "Travelers"},
                )
            else:
                chart = px.bar(
                    rating_counts,
                    x="Rating",
                    y="Count",
                    color_discrete_sequence=["#073b70"],
                    labels={"Count": "Travelers"},
                )
            chart.update_layout(template="plotly_white", height=300, margin=dict(t=8, b=30))
            chart.update_xaxes(tickangle=-35)
            st.plotly_chart(chart, width="stretch", key="overview_ratings")
        st.page_link(ratings_page, label="Open Traveler Ratings")

    st.page_link(flight_dates_page, label="Open Traveler Flight Dates")

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
        tables = chart_tables(filtered, fields)
        answer = local_answer(question, filtered, fields, tables)
        st.session_state.chat_history.extend([
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ])
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            st.write(answer)


def _render_ratings():
    st.title("Operation Epic Fury Traveler Ratings")
    if _show_empty_data():
        return
    rating_column, status_column = fields["rating"], fields["status"]
    if not rating_column or not status_column:
        st.info("Select rating and status fields in the sidebar to show this chart.")
        return
    groups = [status_column, rating_column]
    if fields["direction"]:
        groups.append(fields["direction"])
    counts = _count_table(groups)
    if counts is None or counts.empty:
        st.info("No named travelers are available for this chart.")
        return
    counts = counts.rename(columns={status_column: "Status", rating_column: "Rating"})
    color = "Rating"
    if fields["direction"]:
        counts = counts.rename(columns={fields["direction"]: "Direction"})
    chart = px.bar(
        counts,
        x="Status",
        y="Count",
        color=color,
        barmode="group",
        hover_data=["Direction"] if fields["direction"] else None,
        color_discrete_sequence=["#073b70", "#c5a500", "#b6243d", "#8c8c8c"],
        labels={"Count": "Travelers"},
    )
    chart.update_layout(template="plotly_white", height=530)
    st.plotly_chart(chart, width="stretch", key="ratings_detail")
    st.caption("Counts are distinct travelers, grouped by status and rating. Sidebar filters apply.")
    st.dataframe(counts, width="stretch", hide_index=True)
    st.page_link(home_page, label="Back to dashboard")


def _render_flight_dates():
    st.title("Operation Epic Fury Traveler Flight Dates")
    if _show_empty_data():
        return
    date_column = fields["date"]
    if not date_column:
        st.info("Select an expected movement date field in the sidebar to show this chart.")
        return
    dated = filtered.copy()
    dated["Flight date"] = parse_movement_dates(dated[date_column])
    dated = dated[dated["Flight date"].notna()]
    if dated.empty:
        st.info("No valid flight dates are available for this chart.")
        return
    direction_column = fields["direction"]
    groups = ["Flight date"]
    if direction_column:
        groups.append(direction_column)
    counts = grouped_traveler_counts(dated, groups, fields["traveler"])
    if counts is None or counts.empty:
        st.info("No named travelers with valid flight dates are available.")
        return
    traveler_column = fields["traveler"]
    if traveler_column:
        names = dated[groups + [traveler_column]].copy()
        for column in groups:
            names[column] = names[column].astype("string").fillna("").str.strip().replace(
                "", "Missing"
            )
        names["Traveler"] = names[traveler_column].fillna("").astype(str).str.strip().str.replace(
            r"\s+", " ", regex=True
        )
        names["Name key"] = names["Traveler"].str.casefold()
        names = names[names["Name key"] != ""].drop_duplicates(groups + ["Name key"])
        traveler_names = (
            names.groupby(groups, sort=False)["Traveler"]
            .agg(", ".join)
            .rename("Traveler names")
            .reset_index()
        )
        counts = counts.merge(traveler_names, on=groups, how="left")
    if direction_column:
        counts = counts.rename(columns={direction_column: "Direction"})
        chart = px.bar(
            counts,
            x="Flight date",
            y="Count",
            color="Direction",
            barmode="group",
            hover_data=["Traveler names"] if traveler_column else None,
            color_discrete_sequence=["#073b70", "#c5a500", "#b6243d"],
            labels={"Count": "Travelers"},
        )
    else:
        chart = px.bar(
            counts,
            x="Flight date",
            y="Count",
            hover_data=["Traveler names"] if traveler_column else None,
            color_discrete_sequence=["#073b70"],
            labels={"Count": "Travelers"},
        )
    chart.update_layout(template="plotly_white", height=420)
    st.plotly_chart(chart, width="stretch", key="flight_dates_detail")

    table = dated.copy()
    table["Year"] = table["Flight date"].dt.year
    table["Month"] = table["Flight date"].dt.strftime("%B")
    table["Day"] = table["Flight date"].dt.day
    preferred = [
        "Year",
        "Month",
        "Day",
        fields["traveler"],
        fields["rating"],
        fields["direction"],
        fields["location"],
        fields["vessel"],
        "COMMENTS & ACTIONS",
    ]
    visible = [column for column in preferred if column and column in table.columns]
    st.dataframe(table[visible], width="stretch", hide_index=True)
    st.caption(f"Baseline: {date_column}. Missing and invalid dates are excluded.")
    st.page_link(home_page, label="Back to dashboard")


def _render_status():
    st.title("Operation Epic Fury CIVMAR Tracker")
    if _show_empty_data():
        return
    status_column, direction_column = fields["status"], fields["direction"]
    if not status_column:
        st.info("Select a status field in the sidebar to show this chart.")
        return
    groups = [column for column in (direction_column, status_column) if column]
    counts = _count_table(groups)
    if counts is None or counts.empty:
        st.info("No named travelers are available for this chart.")
        return
    if direction_column:
        counts = counts.rename(columns={direction_column: "Direction"})
    counts = counts.rename(columns={status_column: "Status"})
    chart = px.bar(
        counts,
        x="Direction" if direction_column else "Status",
        y="Count",
        color="Status",
        barmode="group",
        color_discrete_sequence=["#b6243d", "#073b70", "#c5a500", "#c9c9c9", "#777777"],
        labels={"Count": "Travelers"},
    )
    chart.update_layout(template="plotly_white", height=570)
    st.plotly_chart(chart, width="stretch", key="status_detail")
    st.caption("Counts are distinct travelers grouped by direction and status. Sidebar filters apply.")
    st.dataframe(counts, width="stretch", hide_index=True)
    st.page_link(home_page, label="Back to dashboard")


home_page = st.Page(_render_overview, title="CIVMAR Tracker", default=True)
ratings_page = st.Page(_render_ratings, title="Traveler Ratings")
flight_dates_page = st.Page(_render_flight_dates, title="Traveler Flight Dates")
status_page = st.Page(_render_status, title="CIVMAR by Status")
selected_page = st.navigation(
    [home_page, ratings_page, flight_dates_page, status_page],
    position="hidden",
)

with st.sidebar:
    st.header("Upload travel data")
    uploads = st.file_uploader(
        "Upload one or more files", type=SUPPORTED_TYPES, accept_multiple_files=True
    )
    st.caption("Analysis and chat run locally; uploaded data is not sent to an AI service.")

data, errors = load_uploads(uploads)
for error in errors:
    st.error(error)

columns = [column for column in data.columns if column != "Source file"]
options = [None, *columns]
defaults = {
    "status": ("status", "travel status"),
    "traveler": ("civmar/per", "traveler", "traveller", "traveler name", "name"),
    "vessel": ("vessel", "ship", "ship name"),
    "date": ("date 1", "expected date", "planned date", "travel date"),
    "location": ("location", "destination", "port"),
    "direction": ("in/out", "direction"),
    "rating": ("rating",),
    "lodging": ("lodging",),
}
with st.sidebar:
    st.header("Chart fields")
    st.caption("Check detected fields or select the appropriate columns.")
    fields = {}
    for key, label in [
        ("status", "Status"),
        ("traveler", "Traveler name or ID"),
        ("vessel", "Vessel"),
        ("date", "Expected movement date"),
        ("location", "Location"),
        ("direction", "Direction"),
        ("rating", "Rating"),
        ("lodging", "Lodging"),
    ]:
        default = default_field(columns, defaults[key])
        fields[key] = st.selectbox(
            label,
            options,
            index=options.index(default),
            format_func=lambda value: value or "Not selected",
        )

    st.header("Filters")
    filtered = data
    for key in ("status", "vessel", "location", "direction", "rating"):
        column = fields[key]
        if column:
            labels = filtered[column].fillna("").astype(str).str.strip().replace("", "Missing")
            choices = sorted(labels.unique())
            selected = st.multiselect(
                f"Filter by {key}",
                choices,
                key=f"filter_{key}",
            )
            if selected:
                filtered = filtered.loc[labels.isin(selected)]

st.caption(f"{len(filtered):,} movement rows from {len(uploads):,} uploaded file(s).")
selected_page.run()
