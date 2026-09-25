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
# -------------------------------------------------------------------
# Movement-data cleaning and dashboard rendering
# Paste everything below this line after read_upload(...)
# -------------------------------------------------------------------

NULL_MARKERS = {
    "",
    " ",
    "N/A",
    "NA",
    "NAN",
    "NONE",
    "NULL",
    "TBD",
    "TBA",
    "STAND BY",
    "#REF!",
}


def clean_text(series):
    cleaned = (
        series.astype("string")
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    return cleaned.mask(
        cleaned.str.upper().isin(NULL_MARKERS),
        pd.NA,
    )


def clean_movement_data(frame):
    """
    Preserve the original movement data while adding clean analytical fields.
    The function does not invent travel dates, locations, vessels, routes,
    personnel details, or other operational facts.
    """

    data = frame.copy()

    # Normalize column names.
    data.columns = [
        str(column)
        .strip()
        .upper()
        .replace("\n", " ")
        .replace("  ", " ")
        for column in data.columns
    ]

    # Ensure expected fields exist even if source data omits them.
    expected_columns = [
        "STATUS",
        "EXT STATUS",
        "SEX",
        "CIVMAR/PER",
        "RATING",
        "CIVMAR IN/OUT",
        "IN/OUT",
        "VESSEL",
        "LOCATION",
        "START",
        "LEG 1",
        "DATE 1",
        "LEG 2",
        "DATE 2",
        "DOA",
        "DUE OFF DT",
        "O/D",
        "LODGING",
        "LILP SHP",
        "LILP DATE",
        "COMMENTS & ACTIONS",
    ]

    for column in expected_columns:
        if column not in data.columns:
            data[column] = pd.NA

    # Clean all source text values.
    for column in data.columns:
        data[column] = clean_text(data[column])

    # Keep source fields for traceability.
    data["STATUS RAW"] = data["STATUS"]
    data["O/D SOURCE"] = data["O/D"]

    # Normalize dashboard fields.
    for column in [
        "STATUS",
        "EXT STATUS",
        "IN/OUT",
        "VESSEL",
        "LOCATION",
        "START",
        "LEG 1",
        "RATING",
    ]:
        data[column] = data[column].str.upper()

    data["IN/OUT"] = data["IN/OUT"].replace(
        {
            "IN": "GOING",
            "OUT": "LEAVING",
            "ARRIVING": "GOING",
            "DEPARTING": "LEAVING",
        }
    )

    # Parse dates without overwriting the original source fields.
    for column in ["DATE 1", "DATE 2", "DOA", "DUE OFF DT", "LILP DATE"]:
        data[f"{column} PARSED"] = pd.to_datetime(
            data[column],
            errors="coerce",
        )

    data["O/D NUMERIC"] = pd.to_numeric(
        data["O/D"],
        errors="coerce",
    )

    # Consolidate status categories.
    def status_group(status):
        if pd.isna(status):
            return "UNKNOWN"

        status = str(status).upper()

        if "CANCEL" in status:
            return "CANCELLED"

        if "NO SHOW" in status:
            return "NO SHOW"

        if "LOA" in status:
            return "LOA ACTION REQUIRED"

        if "TRANSIT" in status:
            return "IN TRANSIT"

        if "ARRIVAL PENDING" in status:
            return "ARRIVAL PENDING"

        if "ON LOCATION" in status:
            return "ON LOCATION"

        if "TRAVEL CONFIRMED" in status:
            return "TRAVEL CONFIRMED"

        if "STANDBY" in status:
            return "STANDBY PASSENGER"

        if "PENDING" in status:
            return "PENDING"

        if "FLAGGED" in status:
            return "FLAGGED"

        return "OTHER"

    data["STATUS GROUP"] = data["STATUS"].map(status_group)

    data["IS FLAGGED"] = (
        data["EXT STATUS"]
        .fillna("")
        .str.contains("FLAGGED", case=False, regex=False)
        | data["STATUS"]
        .fillna("")
        .str.contains("FLAGGED", case=False, regex=False)
    )

    # Analytical labels. These do not alter raw source fields.
    data["VESSEL ANALYTIC"] = data["VESSEL"].fillna("UNASSIGNED / UNKNOWN")
    data["LOCATION ANALYTIC"] = data["LOCATION"].fillna("UNKNOWN")
    data["DIRECTION ANALYTIC"] = data["IN/OUT"].fillna("UNKNOWN")
    data["PRIMARY ROUTE"] = data["LEG 1"].fillna("UNSCHEDULED")

    # Prefer DATE 1 as the planned movement date.
    data["PLANNED MOVEMENT DATE"] = data["DATE 1 PARSED"]

    # For leaving records without a flight date, use due-off date only as
    # a clearly labeled planning proxy.
    leaving_proxy = (
        data["PLANNED MOVEMENT DATE"].isna()
        & data["DUE OFF DT PARSED"].notna()
        & data["IN/OUT"].eq("LEAVING")
    )

    data.loc[
        leaving_proxy,
        "PLANNED MOVEMENT DATE",
    ] = data.loc[
        leaving_proxy,
        "DUE OFF DT PARSED",
    ]

    data["MOVEMENT DATE SOURCE"] = np.where(
        data["DATE 1 PARSED"].notna(),
        "Travel date",
        np.where(
            leaving_proxy,
            "Due-off date proxy",
            "Unscheduled",
        ),
    )

    # Overdue calculations.
    data["DAYS TO DUE OFF"] = (
        data["DUE OFF DT PARSED"] - AS_OF_DATE
    ).dt.days

    data["DAYS OVERDUE CALCULATED"] = np.where(
        data["DAYS TO DUE OFF"].notna(),
        np.maximum(-data["DAYS TO DUE OFF"], 0),
        np.nan,
    )

    data["O/D CLEAN"] = data["O/D NUMERIC"].fillna(
        data["DAYS OVERDUE CALCULATED"]
    )

    # Movement planning windows.
    days_to_move = (
        data["PLANNED MOVEMENT DATE"] - AS_OF_DATE
    ).dt.days

    data["FORECAST WINDOW"] = np.select(
        [
            data["PLANNED MOVEMENT DATE"].isna(),
            days_to_move < 0,
            days_to_move.between(0, 7),
            days_to_move.between(8, 14),
            days_to_move.between(15, 30),
            days_to_move > 30,
        ],
        [
            "UNSCHEDULED",
            "PAST-DUE / VERIFY",
            "NEXT 7 DAYS",
            "8–14 DAYS",
            "15–30 DAYS",
            "31+ DAYS",
        ],
        default="UNSCHEDULED",
    )

    data["MOVEMENT WEEK"] = (
        data["PLANNED MOVEMENT DATE"]
        .dt.to_period("W-MON")
        .astype("string")
    )

    # Identify records usable for future movement-demand trends.
    data["FORECAST ELIGIBLE"] = (
        data["PLANNED MOVEMENT DATE"].notna()
        & ~data["STATUS GROUP"].isin(
            [
                "CANCELLED",
                "NO SHOW",
                "ON LOCATION",
            ]
        )
    )

    # Data-quality flags.
    quality_flags = pd.Series(
        "",
        index=data.index,
        dtype="string",
    )

    def add_flag(mask, label):
        nonlocal quality_flags

        mask = mask.fillna(False)

        quality_flags = pd.Series(
            np.where(
                mask,
                np.where(
                    quality_flags == "",
                    label,
                    quality_flags + " | " + label,
                ),
                quality_flags,
            ),
            index=data.index,
            dtype="string",
        )

    add_flag(
        data["DOA PARSED"].notna()
        & data["DATE 1 PARSED"].notna()
        & (data["DOA PARSED"] < data["DATE 1 PARSED"]),
        "CHECK DATE CONFLICT",
    )

    add_flag(
        data["STATUS GROUP"].isin(
            [
                "PENDING",
                "TRAVEL CONFIRMED",
                "IN TRANSIT",
                "ARRIVAL PENDING",
                "STANDBY PASSENGER",
            ]
        )
        & data["PLANNED MOVEMENT DATE"].isna(),
        "SCHEDULE DATE MISSING",
    )

    add_flag(
        data["STATUS GROUP"].isin(
            [
                "PENDING",
                "TRAVEL CONFIRMED",
                "IN TRANSIT",
                "ARRIVAL PENDING",
            ]
        )
        & data["PRIMARY ROUTE"].eq("UNSCHEDULED"),
        "ROUTE MISSING",
    )

    add_flag(
        data["STATUS GROUP"].eq("PENDING")
        & data["DAYS OVERDUE CALCULATED"].fillna(0).gt(0),
        "OVERDUE PENDING",
    )

    comments = data["COMMENTS & ACTIONS"].fillna("").str.upper()

    add_flag(
        comments.str.contains(
            r"CONFIRM|AWAITING|UPDATED FLIGHT|NO SHOW",
            regex=True,
        ),
        "COMMENT REVIEW REQUIRED",
    )

    data["DATA QUALITY FLAGS"] = quality_flags.replace("", pd.NA)

    data["ATTENTION PRIORITY"] = np.select(
        [
            data["STATUS GROUP"].isin(
                [
                    "NO SHOW",
                    "ARRIVAL PENDING",
                ]
            ),
            data["DATA QUALITY FLAGS"]
            .fillna("")
            .str.contains("OVERDUE PENDING", regex=False),
            data["IS FLAGGED"],
            data["FORECAST WINDOW"].eq("NEXT 7 DAYS"),
        ],
        [
            "HIGH",
            "HIGH",
            "MEDIUM",
            "MEDIUM",
        ],
        default="ROUTINE",
    )

    return data


def apply_chart_theme(chart):
    chart.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(21,29,63,.42)",
        font=dict(color="#f8fafc", size=13),
        title=dict(font=dict(color="#ffffff", size=19)),
        margin=dict(l=30, r=30, t=65, b=45),
    )

    return chart


def empty_chart(title, message):
    chart = go.Figure()

    chart.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font=dict(color="#ffffff", size=16),
    )

    chart.update_layout(title=title)
    chart.update_xaxes(visible=False)
    chart.update_yaxes(visible=False)

    return apply_chart_theme(chart)


def build_scatter_chart(data):
    forecast_data = data[
        data["FORECAST ELIGIBLE"]
        & data["PLANNED MOVEMENT DATE"].notna()
    ].copy()

    if forecast_data.empty:
        return empty_chart(
            "Scheduled Movement Volume Trend",
            "No forecast-eligible records have a usable planned movement date.",
        )

    daily = (
        forecast_data
        .groupby("PLANNED MOVEMENT DATE")
        .size()
        .reset_index(name="MOVEMENT COUNT")
        .sort_values("PLANNED MOVEMENT DATE")
    )

    chart = go.Figure()

    chart.add_trace(
        go.Scatter(
            x=daily["PLANNED MOVEMENT DATE"],
            y=daily["MOVEMENT COUNT"],
            mode="markers",
            name="Scheduled movements",
            marker=dict(
                size=12,
                color="#ec4899",
                line=dict(color="#ffffff", width=1),
            ),
        )
    )

    if len(daily) >= 2:
        x_numeric = daily["PLANNED MOVEMENT DATE"].map(
            pd.Timestamp.toordinal
        ).to_numpy()

        y_numeric = daily["MOVEMENT COUNT"].to_numpy()

        slope, intercept = np.polyfit(
            x_numeric,
            y_numeric,
            1,
        )

        trend_y = slope * x_numeric + intercept

        correlation = np.corrcoef(
            x_numeric,
            y_numeric,
        )[0, 1]

        r_squared = (
            correlation ** 2
            if not np.isnan(correlation)
            else np.nan
        )

        direction = "increasing" if slope >= 0 else "decreasing"

        chart.add_trace(
            go.Scatter(
                x=daily["PLANNED MOVEMENT DATE"],
                y=trend_y,
                mode="lines",
                name="Linear trend",
                line=dict(color="#22d3ee", width=4),
            )
        )

        chart.add_annotation(
            x=0.02,
            y=0.98,
            xref="paper",
            yref="paper",
            xanchor="left",
            yanchor="top",
            text=(
                f"<b>{direction.title()} volume trend</b><br>"
                f"Slope: {slope:.3f} movements/day<br>"
                f"R²: {r_squared:.2f}"
            ),
            showarrow=False,
            bgcolor="rgba(10,14,39,.88)",
            bordercolor="#22d3ee",
            borderwidth=1,
            font=dict(color="#ffffff", size=13),
        )

    chart.update_layout(
        title="Scheduled Movement Volume Trend",
        xaxis_title="Planned movement date",
        yaxis_title="Scheduled movement count",
    )

    return apply_chart_theme(chart)


def build_heatmap_chart(data):
    forecast_data = data[
        data["FORECAST ELIGIBLE"]
    ].copy()

    if forecast_data.empty:
        return empty_chart(
            "Vessel and Forecast-Window Heatmap",
            "No forecast-eligible records are available.",
        )

    forecast_order = [
        "NEXT 7 DAYS",
        "8–14 DAYS",
        "15–30 DAYS",
        "31+ DAYS",
        "PAST-DUE / VERIFY",
        "UNSCHEDULED",
    ]

    pivot = pd.crosstab(
        forecast_data["VESSEL ANALYTIC"],
        forecast_data["FORECAST WINDOW"],
    )

    for column in forecast_order:
        if column not in pivot.columns:
            pivot[column] = 0

    pivot = pivot[forecast_order]

    top_vessels = (
        pivot.sum(axis=1)
        .sort_values(ascending=False)
        .head(12)
        .index
    )

    pivot = pivot.loc[top_vessels]

    chart = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=pivot.columns,
            y=pivot.index,
            colorscale=[
                [0.00, "#1e1b4b"],
                [0.20, "#6d28d9"],
                [0.40, "#db2777"],
                [0.60, "#f97316"],
                [0.80, "#22d3ee"],
                [1.00, "#14b8a6"],
            ],
            colorbar=dict(
                title="Records",
                tickfont=dict(color="#ffffff"),
                titlefont=dict(color="#ffffff"),
            ),
            hovertemplate=(
                "Vessel: %{y}<br>"
                "Forecast window: %{x}<br>"
                "Movement count: %{z}"
                "<extra></extra>"
            ),
        )
    )

    chart.update_layout(
        title="Vessel and Forecast-Window Heatmap",
        xaxis_title="Forecast window",
        yaxis_title="Vessel",
    )

    return apply_chart_theme(chart)


def build_bar_chart(data):
    forecast_data = data[
        data["FORECAST ELIGIBLE"]
        & data["PLANNED MOVEMENT DATE"].notna()
    ].copy()

    if forecast_data.empty:
        return empty_chart(
            "Upcoming Weekly Movement Demand",
            "No dated forecast-eligible records are available.",
        )

    forecast_data["WEEK START"] = (
        forecast_data["PLANNED MOVEMENT DATE"]
        .dt.to_period("W-MON")
        .apply(lambda period: period.start_time)
    )

    weekly = (
        forecast_data
        .groupby("WEEK START")
        .size()
        .reset_index(name="MOVEMENT COUNT")
        .sort_values("WEEK START")
        .head(12)
    )

    chart = go.Figure(
        data=go.Bar(
            x=weekly["WEEK START"],
            y=weekly["MOVEMENT COUNT"],
            marker=dict(
                color=weekly["MOVEMENT COUNT"],
                colorscale=[
                    [0.00, "#312e81"],
                    [0.35, "#7c3aed"],
                    [0.65, "#ec4899"],
                    [1.00, "#22d3ee"],
                ],
                line=dict(color="#ffffff", width=.5),
            ),
            hovertemplate=(
                "Week beginning: %{x|%d %b %Y}<br>"
                "Scheduled movements: %{y}"
                "<extra></extra>"
            ),
        )
    )

    chart.update_layout(
        title="Upcoming Weekly Movement Demand",
        xaxis_title="Week beginning",
        yaxis_title="Scheduled movement count",
        showlegend=False,
    )

    return apply_chart_theme(chart)


# -------------------------------------------------------------------
# Visible Streamlit application begins here
# -------------------------------------------------------------------
st.title("⚓ SMOM Interactive")

st.caption(
    "Movement-data cleaning, quality review, and forecast-oriented visual analysis."
)

uploaded_file = st.file_uploader(
    "Upload CURRENT MOVEMENT DATA.xlsx or a compatible movement-data file",
    type=SUPPORTED_TYPES,
)

if uploaded_file is None:
    st.info(
        "Upload the Excel movement-data workbook to generate the dashboard, "
        "cleaned dataset, and downloadable final CSV."
    )
    st.stop()

try:
    raw_data = read_upload(
        uploaded_file.name,
        uploaded_file.getvalue(),
    )

    cleaned_data = clean_movement_data(raw_data)

except Exception as exc:
    st.error(
        "The file could not be read or processed. Confirm that the workbook "
        "contains a worksheet with STATUS, VESSEL, and LOCATION columns."
    )

    with st.expander("Technical error details"):
        st.code(str(exc))

    st.stop()


# -------------------------------------------------------------------
# Sidebar filters
# -------------------------------------------------------------------
with st.sidebar:
    st.header("Movement Filters")

    status_options = sorted(
        cleaned_data["STATUS GROUP"]
        .dropna()
        .unique()
        .tolist()
    )

    chosen_statuses = st.multiselect(
        "Status group",
        status_options,
        default=status_options,
    )

    vessel_options = sorted(
        cleaned_data["VESSEL ANALYTIC"]
        .dropna()
        .unique()
        .tolist()
    )

    chosen_vessels = st.multiselect(
        "Vessel",
        vessel_options,
        default=vessel_options,
    )

    window_options = [
        "NEXT 7 DAYS",
        "8–14 DAYS",
        "15–30 DAYS",
        "31+ DAYS",
        "PAST-DUE / VERIFY",
        "UNSCHEDULED",
    ]

    chosen_windows = st.multiselect(
        "Forecast window",
        window_options,
        default=window_options,
    )


filtered_data = cleaned_data.copy()

if chosen_statuses:
    filtered_data = filtered_data[
        filtered_data["STATUS GROUP"].isin(chosen_statuses)
    ]

if chosen_vessels:
    filtered_data = filtered_data[
        filtered_data["VESSEL ANALYTIC"].isin(chosen_vessels)
    ]

if chosen_windows:
    filtered_data = filtered_data[
        filtered_data["FORECAST WINDOW"].isin(chosen_windows)
    ]


# -------------------------------------------------------------------
# Metrics
# -------------------------------------------------------------------
forecast_eligible = int(
    filtered_data["FORECAST ELIGIBLE"].sum()
)

overdue = int(
    filtered_data["DAYS OVERDUE CALCULATED"]
    .fillna(0)
    .gt(0)
    .sum()
)

high_attention = int(
    filtered_data["ATTENTION PRIORITY"]
    .eq("HIGH")
    .sum()
)

quality_flags = int(
    filtered_data["DATA QUALITY FLAGS"]
    .notna()
    .sum()
)

metric_columns = st.columns(4)

metric_columns[0].metric(
    "MOVEMENT RECORDS",
    f"{len(filtered_data):,}",
)

metric_columns[1].metric(
    "FORECAST-ELIGIBLE",
    f"{forecast_eligible:,}",
)

metric_columns[2].metric(
    "OVERDUE / PAST-DUE",
    f"{overdue:,}",
)

metric_columns[3].metric(
    "DATA-QUALITY FLAGS",
    f"{quality_flags:,}",
)

st.info(
    f"Forecast readiness: {forecast_eligible:,} records have a usable planning "
    f"date. {high_attention:,} records are categorized as high attention."
)


# -------------------------------------------------------------------
# Three visual charts appear before chatbot
# -------------------------------------------------------------------
st.subheader("Operational Visual Analysis")

scatter_chart = build_scatter_chart(filtered_data)
heatmap_chart = build_heatmap_chart(filtered_data)
bar_chart = build_bar_chart(filtered_data)

left_column, right_column = st.columns(2)

with left_column:
    st.plotly_chart(
        scatter_chart,
        use_container_width=True,
    )

with right_column:
    st.plotly_chart(
        heatmap_chart,
        use_container_width=True,
    )

st.plotly_chart(
    bar_chart,
    use_container_width=True,
)


# -------------------------------------------------------------------
# Local chatbot appears below all three visualizations
# -------------------------------------------------------------------
with st.expander("Ask the SMOM Data Assistant", expanded=True):
    st.caption(
        "This local assistant uses statistics from the uploaded dataset only."
    )

    if "smom_chat_history" not in st.session_state:
        st.session_state.smom_chat_history = []

    for message in st.session_state.smom_chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    question = st.chat_input(
        "Ask about overdue records, pending movement, trends, or data quality…"
    )

    if question:
        q = question.lower()

        if "overdue" in q:
            answer = (
                f"There are {overdue:,} records with a calculated overdue "
                "condition based on the due-off date."
            )

        elif "pending" in q:
            pending_count = int(
                filtered_data["STATUS GROUP"]
                .eq("PENDING")
                .sum()
            )

            answer = (
                f"There are {pending_count:,} pending movement records in "
                "the current filtered dataset."
            )

        elif "flag" in q or "quality" in q:
            answer = (
                f"There are {quality_flags:,} records with one or more "
                "data-quality flags requiring review."
            )

        elif "trend" in q or "chart" in q:
            answer = (
                "The scatter chart shows scheduled movement volume and a linear "
                "trendline. The heatmap shows vessel demand by forecast window. "
                "The bar chart shows upcoming weekly movement demand."
            )

        else:
            answer = (
                "I can help with pending movements, overdue conditions, "
                "forecast windows, data-quality flags, and chart interpretation."
            )

        st.session_state.smom_chat_history.append(
            {
                "role": "user",
                "content": question,
            }
        )

        st.session_state.smom_chat_history.append(
            {
                "role": "assistant",
                "content": answer,
            }
        )

        st.rerun()


# -------------------------------------------------------------------
# Final cleaned-data download and attention queue
# -------------------------------------------------------------------
with st.expander("Attention Queue and Final Cleaned Data", expanded=False):
    attention_queue = filtered_data[
        filtered_data["ATTENTION PRIORITY"].isin(
            [
                "HIGH",
                "MEDIUM",
            ]
        )
    ].copy()

    st.subheader("Attention Queue")

    st.dataframe(
        attention_queue.head(250),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Final Cleaned Movement Dataset")

    st.caption(
        "The cleaned dataset retains original columns and adds forecasting, "
        "overdue, trend, and data-quality fields."
    )

    st.dataframe(
        filtered_data.head(500),
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        label="Download Cleaned Movement Data",
        data=filtered_data.to_csv(index=False).encode("utf-8"),
        file_name="SMOM_Interactive_cleaned_movement_data.csv",
        mime="text/csv",
    )

    st.download_button(
        label="Download Attention Queue",
        data=attention_queue.to_csv(index=False).encode("utf-8"),
        file_name="SMOM_Interactive_attention_queue.csv",
        mime="text/csv",
    )

st.caption(
    "Verify source records and flagged data-quality issues before using outputs "
    "for operational decisions."
)
