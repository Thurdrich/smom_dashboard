from io import BytesIO
from pathlib import Path
import re

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


st.set_page_config(
    page_title="SMOM Interactive",
    page_icon="⚓",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
:root {
    --bg:#0a0e27;
    --panel:#151d3f;
    --purple:#a855f7;
    --cyan:#06b6d4;
    --pink:#ec4899;
    --text:#f0f9ff;
    --muted:#cbd5e1;
}

.stApp {
    background:linear-gradient(135deg,var(--bg),#1a1f4b 50%,#2d1b69);
    color:var(--text);
}

.block-container {
    max-width:1500px;
    padding-top:1.5rem;
}

[data-testid="stSidebar"] {
    background:linear-gradient(180deg,#0f1533,#1a0f3d);
    border-right:2px solid var(--purple);
}

[data-testid="stSidebar"] * {
    color:var(--text);
}

[data-testid="stMetric"] {
    background:linear-gradient(
        145deg,
        rgba(168,85,247,.12),
        rgba(6,182,212,.08)
    );
    border:1px solid var(--purple);
    border-radius:12px;
    padding:14px;
    box-shadow:0 0 18px rgba(168,85,247,.14);
}

[data-testid="stMetricLabel"] {
    color:#67e8f9 !important;
    font-weight:700;
}

[data-testid="stMetricValue"] {
    color:#fff !important;
}

.insight {
    background:linear-gradient(
        110deg,
        rgba(126,34,206,.2),
        rgba(6,182,212,.12)
    );
    border:1px solid var(--cyan);
    border-left:5px solid var(--purple);
    border-radius:10px;
    padding:15px 18px;
    color:var(--text);
}

.stMarkdown,
.stCaption,
[data-testid="stCaptionContainer"] {
    color:var(--muted);
}

label {
    color:var(--text) !important;
}

[data-baseweb="select"] > div,
[data-baseweb="input"] > div {
    background:rgba(15,21,51,.9);
    color:var(--text);
    border:1px solid var(--cyan) !important;
}

[data-baseweb="select"] input,
[data-baseweb="select"] span,
[data-baseweb="input"] input {
    color:var(--text) !important;
}

[data-testid="stExpander"] {
    border:1px solid rgba(168,85,247,.5);
    background:rgba(21,29,63,.55);
}

h1,
h2,
h3 {
    color:#fff !important;
    text-shadow:0 0 10px rgba(168,85,247,.3);
}

/* Improve sidebar/menu readability */
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] .stCaption {
    color:#ffffff !important;
    font-size:1rem !important;
    font-weight:700 !important;
}

/* Improve select and multiselect menu text */
[data-testid="stSidebar"] [data-baseweb="select"] div,
[data-testid="stSidebar"] [data-baseweb="select"] span,
[data-testid="stSidebar"] [data-baseweb="select"] input {
    color:#ffffff !important;
    font-size:1rem !important;
    font-weight:650 !important;
}

/* Improve upload-area readability */
[data-testid="stFileUploaderDropzone"] {
    background:rgba(6,182,212,.10) !important;
    border:2px dashed #22d3ee !important;
}

[data-testid="stFileUploaderDropzoneInstructions"] span,
[data-testid="stFileUploaderDropzoneInstructions"] small {
    color:#ffffff !important;
    font-size:1rem !important;
    font-weight:700 !important;
}

/* Make upload button more visible */
[data-testid="stFileUploaderDropzone"] button,
[data-testid="stFileUploader"] button {
    background:linear-gradient(90deg,#a855f7,#06b6d4) !important;
    color:#ffffff !important;
    font-size:1rem !important;
    font-weight:800 !important;
    border:1px solid #ffffff !important;
    border-radius:8px !important;
}

/* Bright sidebar headings */
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color:#67e8f9 !important;
    font-weight:800 !important;
}
</style>
""",
    unsafe_allow_html=True,
)

SUPPORTED_TYPES = ["csv", "xlsx", "xls", "json", "parquet", "xml"]

DATE_WORDS = (
    "date",
    "dt",
    "day",
    "time",
    "start",
    "end",
    "arrival",
    "departure",
    "request",
    "created",
    "received",
    "distributed",
)

SENSITIVE_WORDS = (
    r"name|employee|person|lname|fname|first.?name|last.?name|"
    r"civmar.?/per"
)


def demo_data():
    rng = np.random.default_rng(7)

    dates = pd.date_range(
        end=pd.Timestamp.today().normalize(),
        periods=180,
        freq="D",
    )

    workload = rng.normal(72, 18, 180).clip(10, 140).round(1)
    staffing = (workload * rng.normal(.91, .12, 180)).clip(5, 150).round(1)

    return pd.DataFrame(
        {
            "Date": dates,
            "Region": rng.choice(
                ["North", "South", "East", "West"],
                180,
            ),
            "Workload": workload,
            "Staffing": staffing,
            "Readiness": (
                100 - (workload - staffing).clip(0) * 1.7
            ).clip(35, 100).round(1),
            "Priority": rng.choice(
                ["Routine", "Elevated", "Critical"],
                180,
                p=[.55, .30, .15],
            ),
        }
    )


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
    frames = []
    errors = []

    for uploaded in files or []:
        try:
            frame = read_upload(
                uploaded.name,
                uploaded.getvalue(),
            ).copy()

            frame.columns = [
                str(column).strip() or f"Column {index + 1}"
                for index, column in enumerate(frame.columns)
            ]

            frame = frame.dropna(how="all").reset_index(drop=True)
            frame["Source file"] = uploaded.name
            frames.append(frame)

        except Exception as exc:
            errors.append(f"{uploaded.name}: {exc}")

    combined = (
        pd.concat(frames, ignore_index=True, sort=False)
        if frames
        else pd.DataFrame()
    )

    return combined, errors


def parse_dates(series, column_name=""):
    clean = series.replace(
        {
            "": np.nan,
            "#REF!": np.nan,
            "STAND BY": np.nan,
        }
    )

    try:
        parsed = pd.to_datetime(clean, errors="coerce")
    except (TypeError, ValueError, OverflowError):

        def parse_one(value):
            if not isinstance(value, (list, tuple, dict, set)) and pd.isna(value):
                return pd.NaT

            try:
                return pd.to_datetime(value, errors="coerce")
            except (TypeError, ValueError, OverflowError):
                return pd.NaT

        parsed = clean.map(parse_one)

    if (
        parsed.notna().mean() < .7
        and pd.api.types.is_numeric_dtype(clean)
    ):
        numeric = pd.to_numeric(clean, errors="coerce")

        excel_dates = pd.to_datetime(
            numeric,
            unit="D",
            origin="1899-12-30",
            errors="coerce",
        )

        if excel_dates.notna().mean() > parsed.notna().mean():
            parsed = excel_dates

    return parsed


def profile(data):
    numeric = []
    dates = []
    categorical = []
    text = []

    for column in data.columns:
        if column == "Source file":
            continue

        series = data[column]
        non_null = data[column].dropna()

        if not len(non_null):
            categorical.append(column)
            continue

        numeric_candidate = pd.to_numeric(
            non_null.astype(str).str.replace(",", "", regex=False),
            errors="coerce",
        )

        date_candidate = parse_dates(series, column)
        name = str(column).lower()

        date_likely = (
            any(word in name for word in DATE_WORDS)
            and date_candidate.notna().mean() >= .35
        )

        if date_likely or (
            date_candidate.notna().mean() >= .85
            and numeric_candidate.notna().mean() < .85
            and non_null.nunique() > 1
        ):
            dates.append(column)

        elif (
            pd.api.types.is_numeric_dtype(series)
            or numeric_candidate.notna().mean() >= .9
        ):
            numeric.append(column)

        elif non_null.nunique() <= min(30, max(10, len(data) * .2)):
            categorical.append(column)

        else:
            text.append(column)

    return numeric, dates, categorical, text


def clean_label(series):
    return (
        series.fillna("Missing")
        .astype(str)
        .str.strip()
        .replace({"": "Missing"})
    )


def best_category(data, categorical):
    usable = [
        column
        for column in categorical
        if 2
        <= data[column].nunique(dropna=True)
        <= min(30, max(5, len(data) // 2))
    ]

    preferred = (
        "status",
        "location",
        "ship",
        "vessel",
        "arrival",
        "departure",
        "employee",
        "type",
        "travel writer",
    )

    if usable:
        return sorted(
            usable,
            key=lambda column: (
                not any(key in column.lower() for key in preferred),
                data[column].nunique(),
            ),
        )[0]

    return categorical[0] if categorical else None


def insights(data, numeric, dates, categorical, text):
    findings = []

    if categorical:
        category = best_category(data, categorical)
        counts = clean_label(data[category]).value_counts()

        if len(counts):
            findings.append(
                f"**{counts.index[0]}** is the largest `{category}` segment "
                f"at **{counts.iloc[0] / len(data):.1%}** of records."
            )

    if dates:
        parsed = parse_dates(data[dates[0]]).dropna()

        if len(parsed):
            findings.append(
                f"`{dates[0]}` spans "
                f"**{parsed.min():%Y-%m-%d} to {parsed.max():%Y-%m-%d}**."
            )

    missing = data.isna().mean().sort_values(ascending=False)

    if len(missing) and missing.iloc[0] >= .25:
        findings.append(
            f"**{missing.index[0]}** is missing in "
            f"**{missing.iloc[0]:.1%}** of rows."
        )

    return (
        " ".join(findings)
        or "Not enough structure for a directional finding; validate the source schema first."
    )


def sensitive_columns(frame):
    return [
        column
        for column in frame.columns
        if re.search(SENSITIVE_WORDS, str(column), re.I)
    ]


def mask_sensitive(frame, columns=None):
    result = frame.copy()

    columns = (
        sensitive_columns(result)
        if columns is None
        else columns
    )

    for column in columns:
        result[column] = result[column].notna().map(
            {
                True: "[present]",
                False: "[missing]",
            }
        )

    return result


def apply_chart_theme(chart):
    chart.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(21,29,63,.42)",
        font=dict(color="#f8fafc", size=14),
        title=dict(font=dict(color="#ffffff", size=20)),
        margin=dict(l=30, r=30, t=65, b=45),
        legend=dict(font=dict(color="#ffffff")),
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
        font=dict(color="#f8fafc", size=16),
    )

    chart.update_xaxes(visible=False)
    chart.update_yaxes(visible=False)
    chart.update_layout(title=title)

    return apply_chart_theme(chart)


def fixed_visuals(data, numeric, categorical):
    """Create scatter/trend, heatmap, and vertical bar charts."""

    numeric_frame = pd.DataFrame()

    for column in numeric:
        numeric_frame[column] = pd.to_numeric(
            data[column]
            .astype(str)
            .str.replace(",", "", regex=False),
            errors="coerce",
        )

    # ---------------------------------------------------------------
    # 1. Scatter chart with visible linear-trend analysis
    # ---------------------------------------------------------------
    if len(numeric) >= 2:
        x_column = numeric[0]
        y_column = numeric[1]

        scatter_data = numeric_frame[
            [x_column, y_column]
        ].dropna()

        if (
            len(scatter_data) >= 2
            and scatter_data[x_column].nunique() > 1
        ):
            slope, intercept = np.polyfit(
                scatter_data[x_column],
                scatter_data[y_column],
                1,
            )

            trend_x = np.linspace(
                scatter_data[x_column].min(),
                scatter_data[x_column].max(),
                100,
            )

            trend_y = slope * trend_x + intercept

            correlation = scatter_data[x_column].corr(
                scatter_data[y_column]
            )

            r_squared = (
                correlation ** 2
                if pd.notna(correlation)
                else np.nan
            )

            direction = "positive" if slope >= 0 else "negative"

            scatter = px.scatter(
                scatter_data,
                x=x_column,
                y=y_column,
                color_discrete_sequence=["#f472b6"],
                title=f"Relationship Analysis: {x_column} vs. {y_column}",
            )

            scatter.add_trace(
                go.Scatter(
                    x=trend_x,
                    y=trend_y,
                    mode="lines",
                    name="Linear trend",
                    line=dict(color="#22d3ee", width=4),
                )
            )

            scatter.add_annotation(
                x=0.02,
                y=0.98,
                xref="paper",
                yref="paper",
                xanchor="left",
                yanchor="top",
                text=(
                    f"<b>{direction.title()} trend</b><br>"
                    f"Slope: {slope:.2f}<br>"
                    f"R²: {r_squared:.2f}"
                ),
                showarrow=False,
                bgcolor="rgba(10,14,39,.88)",
                bordercolor="#22d3ee",
                borderwidth=1,
                font=dict(color="#ffffff", size=13),
            )

            scatter = apply_chart_theme(scatter)

        else:
            scatter = empty_chart(
                "Relationship Analysis",
                "The selected numeric fields do not contain enough usable variation for a trend analysis.",
            )

    else:
        scatter = empty_chart(
            "Relationship Analysis",
            "Upload data containing at least two numeric fields to generate a scatter plot and trendline.",
        )

    # ---------------------------------------------------------------
    # 2. Vivid correlation heatmap
    # ---------------------------------------------------------------
    if len(numeric_frame.columns) >= 2:
        correlation_matrix = numeric_frame.corr(numeric_only=True)

        if correlation_matrix.shape[0] >= 2:
            heatmap = go.Figure(
                data=go.Heatmap(
                    z=correlation_matrix.values,
                    x=correlation_matrix.columns,
                    y=correlation_matrix.index,
                    zmin=-1,
                    zmax=1,
                    colorscale=[
                        [0.00, "#3b0764"],
                        [0.20, "#7e22ce"],
                        [0.40, "#ec4899"],
                        [0.50, "#f8fafc"],
                        [0.65, "#22d3ee"],
                        [0.82, "#06b6d4"],
                        [1.00, "#14b8a6"],
                    ],
                    colorbar=dict(
                        title="Correlation",
                        tickfont=dict(color="#ffffff"),
                        titlefont=dict(color="#ffffff"),
                    ),
                    hovertemplate=(
                        "%{x} × %{y}"
                        "<br>Correlation: %{z:.2f}"
                        "<extra></extra>"
                    ),
                )
            )

            heatmap.update_layout(
                title="Signal Heatmap: Numeric Correlations"
            )

            heatmap = apply_chart_theme(heatmap)

        else:
            heatmap = empty_chart(
                "Signal Heatmap",
                "Not enough numeric fields are available for a correlation heatmap.",
            )

    else:
        heatmap = empty_chart(
            "Signal Heatmap",
            "Upload data containing at least two numeric fields to generate the heatmap.",
        )

    # ---------------------------------------------------------------
    # 3. Traditional vertical bar chart
    # ---------------------------------------------------------------
    category = best_category(data, categorical)

    if category:
        counts = (
            clean_label(data[category])
            .value_counts()
            .head(12)
            .sort_values(ascending=False)
        )

        bar = px.bar(
            x=counts.index,
            y=counts.values,
            labels={
                "x": category,
                "y": "Record count",
            },
            title=f"Category Distribution: {category}",
            color=counts.values,
            color_continuous_scale=[
                "#312e81",
                "#7c3aed",
                "#ec4899",
                "#22d3ee",
            ],
        )

        bar.update_layout(coloraxis_showscale=False)
        bar.update_xaxes(tickangle=-30)
        bar = apply_chart_theme(bar)

    elif numeric:
        metric = numeric[0]

        values = pd.to_numeric(
            data[metric],
            errors="coerce",
        ).dropna().head(20)

        bar = px.bar(
            x=[f"Record {index + 1}" for index in range(len(values))],
            y=values,
            labels={
                "x": "Record",
                "y": metric,
            },
            title=f"Vertical Bar Chart: {metric}",
            color=values,
            color_continuous_scale=[
                "#312e81",
                "#7c3aed",
                "#ec4899",
                "#22d3ee",
            ],
        )

        bar.update_layout(coloraxis_showscale=False)
        bar.update_xaxes(tickangle=-30)
        bar = apply_chart_theme(bar)

    else:
        bar = empty_chart(
            "Category Distribution",
            "Upload a dataset with a category or numeric field to generate a vertical bar chart.",
        )

    return scatter, heatmap, bar


def local_answer(question, data, numeric, dates, categorical):
    q = question.lower().strip()
    category = best_category(data, categorical)

    if any(word in q for word in ("chart", "graph", "visual", "plot")):
        if "line" in q or "trend" in q:
            return (
                "The scatter visualization includes an on-chart linear trendline, "
                "trend direction, slope, and R-squared value."
            )

        if "scatter" in q or "relationship" in q:
            return (
                "The first visualization compares the first two detected numeric "
                "fields and displays their linear relationship."
            )

        if "heatmap" in q or "correlation" in q:
            return (
                "The heatmap shows correlations among detected numeric fields. "
                "Values closer to 1 or -1 indicate stronger relationships."
            )

        if "bar" in q or "distribution" in q:
            return (
                "The vertical bar chart shows the largest segments in the "
                "primary detected category field."
            )

        return (
            "Review the three visualizations above for relationship, correlation, "
            "and category-distribution analysis."
        )

    if "missing" in q or "quality" in q:
        missing = data.isna().mean().sort_values(ascending=False)
        top = missing.head(5)

        return "Missingness: " + "; ".join(
            f"{column} {value:.1%}"
            for column, value in top.items()
        ) + "."

    if "how many" in q or "rows" in q or "records" in q:
        return (
            f"The current filtered dataset contains {len(data):,} rows "
            f"across {len(data.columns):,} fields."
        )

    if "date" in q or "time" in q:
        return (
            f"Detected date fields: {', '.join(dates) if dates else 'none'}."
        )

    if category and (
        "largest" in q
        or "most" in q
        or "category" in q
    ):
        counts = clean_label(data[category]).value_counts()

        if len(counts):
            return (
                f"The largest {category} segment is {counts.index[0]} with "
                f"{counts.iloc[0]:,} records "
                f"({counts.iloc[0] / len(data):.1%})."
            )

    if numeric:
        stats = pd.to_numeric(
            data[numeric[0]],
            errors="coerce",
        ).describe()

        return (
            f"For {numeric[0]}, the mean is "
            f"{stats.get('mean', np.nan):.2f}, median "
            f"{stats.get('50%', np.nan):.2f}, and valid values "
            f"{int(stats.get('count', 0)):,}."
        )

    return (
        "I can answer questions about row counts, missingness, detected dates, "
        "categories, numeric summaries, and the three visualizations."
    )


# -------------------------------------------------------------------
# Sidebar: Uploads and filters
# -------------------------------------------------------------------
with st.sidebar:
    st.header("Upload Your Data")

    uploads = st.file_uploader(
        "Add one or more datasets",
        type=SUPPORTED_TYPES,
        accept_multiple_files=True,
    )

    st.caption(
        "Supported: CSV, Excel, JSON, Parquet, XML. "
        "Files are analyzed in-session."
    )


uploaded_data, errors = load_uploads(uploads)

using_demo = uploaded_data.empty

analysis_data = demo_data() if using_demo else uploaded_data

detected_sensitive = (
    []
    if using_demo
    else sensitive_columns(analysis_data)
)

mask_names = True

if detected_sensitive:
    st.warning(
        "Potential personal identifiers were detected. "
        "Masking is recommended for previews and downloads."
    )

    mask_names = st.radio(
        "Identifier handling",
        (
            "Mask detected fields (recommended)",
            "Continue without masking",
        ),
        key="sensitive_data_choice",
    ).startswith("Mask")


numeric, dates, categorical, text = profile(analysis_data)

with st.sidebar:
    st.subheader("Data Filters")

    selected = {}

    for column in [
        value
        for value in categorical
        if 1 < analysis_data[value].nunique(dropna=True) <= 20
    ][:4]:

        values = sorted(
            clean_label(analysis_data[column]).unique().tolist()
        )

        selected[column] = st.multiselect(
            column,
            values,
            default=values,
        )


filtered = analysis_data.copy()

for column, values in selected.items():
    if values:
        filtered = filtered[
            clean_label(filtered[column]).isin(values)
        ]


# -------------------------------------------------------------------
# Main application display
# -------------------------------------------------------------------
st.title("⚓ SMOM Interactive")

st.caption(
    "Focused operational analysis with a local data assistant—"
    "no external API or data transfer."
)

if using_demo:
    st.info(
        "Preview mode: upload your file to replace the illustrative data."
    )

else:
    st.success(
        f"Analyzing {len(uploads)} file(s), "
        f"{len(filtered):,} filtered rows, and "
        f"{len(filtered.columns):,} fields."
    )

for error in errors:
    st.warning(error)


missing_rate = (
    float(filtered.isna().mean().mean())
    if not filtered.empty
    else 0
)

metrics = st.columns(4)

metrics[0].metric("RECORDS", f"{len(filtered):,}")
metrics[1].metric("FIELDS", f"{len(filtered.columns):,}")
metrics[2].metric(
    "DATE / NUMERIC SIGNALS",
    f"{len(dates)} / {len(numeric)}",
)
metrics[3].metric("MISSING VALUES", f"{missing_rate:.1%}")


st.markdown(
    f"""
<div class="insight">
<strong>
{"Data looks sound for exploration."
if missing_rate < .05
else "Proceed carefully: missingness may distort conclusions."}
</strong>
<br>
{insights(filtered, numeric, dates, categorical, text)}
</div>
""",
    unsafe_allow_html=True,
)


# -------------------------------------------------------------------
# Required visuals appear BEFORE the assistant
# -------------------------------------------------------------------
st.subheader("Operational Visual Analysis")

scatter_chart, heatmap_chart, bar_chart = fixed_visuals(
    filtered,
    numeric,
    categorical,
)

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

st.caption(
    "The scatter plot includes an on-chart linear trendline and trend metrics. "
    "The heatmap displays numeric-field correlations, while the vertical bar "
    "chart displays the primary category distribution."
)


# -------------------------------------------------------------------
# Chatbot scientist / local data assistant BELOW the three visuals
# -------------------------------------------------------------------
with st.expander("Ask the SMOM Data Assistant", expanded=True):
    st.caption(
        "This assistant uses rules and statistics from the current filtered "
        "data only; it does not call an external AI service."
    )

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    question = st.chat_input(
        "Ask about this data or the visual analysis…"
    )

    if question:
        st.session_state.chat_history.append(
            {
                "role": "user",
                "content": question,
            }
        )

        answer = local_answer(
            question,
            filtered,
            numeric,
            dates,
            categorical,
        )

        st.session_state.chat_history.append(
            {
                "role": "assistant",
                "content": answer,
            }
        )

        st.rerun()


# -------------------------------------------------------------------
# Prepared data and exception queue
# -------------------------------------------------------------------
with st.expander("Attention Queue and Prepared Data"):
    exception_columns = [
        column
        for column in text
        if column != "Source file"
    ]

    if exception_columns:
        exception_mask = (
            filtered[exception_columns]
            .fillna("")
            .astype(str)
            .apply(
                lambda column: column.str.contains(
                    r"unable|await|stand.?by|delay|cancel|no.?show|#REF!",
                    case=False,
                    regex=True,
                )
            )
            .any(axis=1)
        )

        queue = filtered.loc[exception_mask]

        st.write(
            f"**{len(queue):,}** rows contain exception markers."
        )

        st.dataframe(
            (
                mask_sensitive(queue.head(200), detected_sensitive)
                if mask_names
                else queue.head(200)
            ),
            use_container_width=True,
            hide_index=True,
        )

    else:
        st.caption("No free-text exception field was detected.")

    prepared = (
        mask_sensitive(filtered, detected_sensitive)
        if mask_names
        else filtered
    )

    st.dataframe(
        prepared.head(500),
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        "Download Prepared View",
        prepared.to_csv(index=False).encode("utf-8"),
        "smom_interactive_prepared_data.csv",
        "text/csv",
    )


if not using_demo:
    st.caption(
        "No-BS rule: charts identify patterns; verify underlying records "
        "before operational decisions."
    )
