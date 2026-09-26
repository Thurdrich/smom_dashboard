import html
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

st.markdown("""
<style>
:root { --bg:#0a0e27; --panel:#151d3f; --purple:#a855f7; --cyan:#06b6d4; --pink:#ec4899; --text:#f0f9ff; --muted:#cbd5e1; }
.stApp { background:linear-gradient(135deg,var(--bg),#1a1f4b 50%,#2d1b69); color:var(--text); }
.block-container { max-width:1500px; padding-top:1.5rem; }
[data-testid="stSidebar"] { background:linear-gradient(180deg,#0f1533,#1a0f3d); border-right:2px solid var(--purple); }
[data-testid="stSidebar"] * { color:var(--text); }
[data-testid="stMetric"] { background:linear-gradient(145deg,rgba(168,85,247,.12),rgba(6,182,212,.08)); border:1px solid var(--purple); border-radius:12px; padding:14px; box-shadow:0 0 18px rgba(168,85,247,.14); }
[data-testid="stMetricLabel"] { color:#67e8f9 !important; font-weight:700; }
[data-testid="stMetricValue"] { color:#fff !important; }
.insight { background:linear-gradient(110deg,rgba(126,34,206,.2),rgba(6,182,212,.12)); border:1px solid var(--cyan); border-left:5px solid var(--purple); border-radius:10px; padding:15px 18px; color:var(--text); }
.stMarkdown,.stCaption,[data-testid="stCaptionContainer"] { color:var(--muted); }
label { color:var(--text) !important; }
[data-baseweb="select"] > div,[data-baseweb="input"] > div { background:rgba(15,21,51,.9); color:var(--text); border:1px solid var(--cyan) !important; }
[data-baseweb="select"] input,[data-baseweb="select"] span,[data-baseweb="input"] input { color:var(--text) !important; }
[data-testid="stExpander"] { border:1px solid rgba(168,85,247,.5); background:rgba(21,29,63,.55); }
h1,h2,h3 { color:#fff !important; text-shadow:0 0 10px rgba(168,85,247,.3); }
.recommendation-card { background:linear-gradient(145deg,rgba(6,182,212,.1),rgba(168,85,247,.1)); border:1px solid rgba(6,182,212,.45); border-left:4px solid var(--cyan); border-radius:12px; padding:14px 16px; margin-bottom:12px; color:var(--text); min-height:150px; }
.recommendation-confidence { display:inline-block; margin-top:8px; padding:2px 8px; border-radius:999px; background:rgba(168,85,247,.2); color:#e9d5ff; font-size:.8rem; font-weight:700; }
</style>
""", unsafe_allow_html=True)

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
                p=[.55, .3, .15],
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

    return (
        pd.concat(frames, ignore_index=True, sort=False)
        if frames
        else pd.DataFrame()
    ), errors


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
            if (
                not isinstance(value, (list, tuple, dict, set))
                and pd.isna(value)
            ):
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

    return (
        sorted(
            usable,
            key=lambda column: (
                not any(
                    key in column.lower()
                    for key in preferred
                ),
                data[column].nunique(),
            ),
        )[0]
        if usable
        else (categorical[0] if categorical else None)
    )


def metric_direction(column_name):
    name = str(column_name).lower().replace("_", " ")

    if any(
        word in name
        for word in (
            "workload",
            "backlog",
            "delay",
            "risk",
            "incident",
            "error",
            "queue",
            "gap",
            "aging",
            "overtime",
            "critical",
            "overdue",
        )
    ):
        return "higher_is_worse"

    if any(
        word in name
        for word in (
            "readiness",
            "staffing",
            "coverage",
            "availability",
            "fill",
            "compliance",
            "capacity",
            "service level",
        )
    ):
        return "higher_is_better"

    return "unknown"


def best_matching_column(data, candidates, include_words, exclude_words=()):
    matches = []

    for column in candidates:
        name = str(column).lower()

        if any(word in name for word in exclude_words):
            continue

        score = sum(word in name for word in include_words)
        if score:
            matches.append(
                (
                    score,
                    data[column].notna().mean(),
                    -data[column].isna().mean(),
                    column,
                )
            )

    return max(matches)[-1] if matches else None


def best_trend_columns(data, numeric, dates):
    date_candidates = []

    for column in dates:
        parsed = parse_dates(data[column])
        date_candidates.append(
            (
                parsed.notna().mean(),
                parsed.nunique(dropna=True),
                column,
            )
        )

    metric_candidates = []

    for column in numeric:
        numeric_values = pd.to_numeric(
            data[column],
            errors="coerce",
        )
        metric_candidates.append(
            (
                metric_direction(column) != "unknown",
                numeric_values.notna().mean(),
                numeric_values.std(skipna=True) > 0,
                column,
            )
        )

    date_column = max(date_candidates)[-1] if date_candidates else None
    metric_column = (
        max(metric_candidates)[-1]
        if metric_candidates
        else None
    )

    return date_column, metric_column


def confidence_label(sample_size, missingness, signal_strength):
    if sample_size < 10 or missingness >= .55:
        return "Low"

    score = 0

    if sample_size >= 120:
        score += 2
    elif sample_size >= 40:
        score += 1

    if missingness <= .1:
        score += 2
    elif missingness <= .25:
        score += 1

    if signal_strength >= .3:
        score += 2
    elif signal_strength >= .15:
        score += 1

    if score >= 5:
        return "High"

    if score >= 3:
        return "Medium"

    return "Low"


def recommendation_record(
    title,
    insight,
    action,
    confidence,
    evidence="",
    priority=0,
):
    if confidence == "Low":
        action = f"Treat this as an early signal: {action}"

    return {
        "title": title,
        "insight": insight,
        "action": action,
        "confidence": confidence,
        "evidence": evidence,
        "_priority": priority,
    }


def recommend_actions(data, numeric, dates, categorical, text):
    if data.empty:
        return [
            {
                "title": "Need more filtered records",
                "insight": "The current filters leave no rows to evaluate.",
                "action": (
                    "Broaden the active filters or upload additional records "
                    "before acting on this view."
                ),
                "confidence": "Low",
                "evidence": "",
            }
        ]

    recommendations = []
    row_count = len(data)
    quality_fields = []

    category = best_category(data, categorical)
    if category and category in data:
        quality_fields.append(category)
        counts = clean_label(data[category]).value_counts()

        if len(counts):
            top_label = counts.index[0]
            top_count = int(counts.iloc[0])
            top_share = top_count / row_count

            if top_share >= .48:
                missingness = data[category].isna().mean()
                signal_strength = min(1.0, top_share - .33)
                confidence = confidence_label(
                    row_count,
                    missingness,
                    signal_strength,
                )
                recommendations.append(
                    recommendation_record(
                        "Concentration warrants segment planning",
                        (
                            f"`{top_label}` accounts for {top_share:.1%} of the current "
                            f"`{category}` volume, which suggests the workload is concentrated "
                            "in one segment."
                        ),
                        (
                            "Bias near-term capacity and review effort toward this segment, "
                            f"then split `{top_label}` by time or other filters to confirm "
                            "which sub-cohort is driving the concentration."
                        ),
                        confidence,
                        evidence=(
                            f"{top_count:,} of {row_count:,} rows fall into `{top_label}`."
                        ),
                        priority=signal_strength,
                    )
                )

    numeric_candidates = [
        column
        for column in numeric
        if column in data.columns
    ]
    workload_column = best_matching_column(
        data,
        numeric_candidates,
        ("workload", "demand", "backlog", "volume", "queue"),
    )
    staffing_column = best_matching_column(
        data,
        [
            column
            for column in numeric_candidates
            if column != workload_column
        ],
        ("staffing", "staff", "manning", "crew", "capacity", "fte"),
    )
    readiness_column = best_matching_column(
        data,
        [
            column
            for column in numeric_candidates
            if column not in {workload_column, staffing_column}
        ],
        ("readiness", "availability", "coverage", "fill"),
    )

    quality_fields.extend(
        [
            column
            for column in (
                workload_column,
                staffing_column,
                readiness_column,
            )
            if column
        ]
    )

    if workload_column and staffing_column:
        workload_values = pd.to_numeric(
            data[workload_column],
            errors="coerce",
        )
        staffing_values = pd.to_numeric(
            data[staffing_column],
            errors="coerce",
        )
        readiness_values = (
            pd.to_numeric(
                data[readiness_column],
                errors="coerce",
            )
            if readiness_column
            else pd.Series(np.nan, index=data.index)
        )

        operations = pd.DataFrame(
            {
                "workload": workload_values,
                "staffing": staffing_values,
                "readiness": readiness_values,
            }
        ).dropna(subset=["workload", "staffing"])

        if len(operations) >= 10:
            operations["gap"] = (
                operations["workload"] - operations["staffing"]
            )
            mean_gap = float(operations["gap"].mean())
            workload_mean = float(
                operations["workload"].mean()
                if operations["workload"].notna().any()
                else 0
            )
            threshold = max(2.0, workload_mean * .08)
            readiness_mean = (
                float(operations["readiness"].mean())
                if operations["readiness"].notna().any()
                else np.nan
            )
            readiness_risk = (
                max(0.0, (85 - readiness_mean) / 20)
                if not pd.isna(readiness_mean)
                else 0.0
            )
            signal_strength = max(
                mean_gap / max(abs(workload_mean), 1.0),
                readiness_risk,
            )
            missingness = 1 - (
                len(operations) / max(len(data), 1)
            )

            if mean_gap >= threshold or readiness_risk >= .15:
                readiness_clause = (
                    f" and `{readiness_column}` averages {readiness_mean:.1f}"
                    if readiness_column and not pd.isna(readiness_mean)
                    else ""
                )
                confidence = confidence_label(
                    len(operations),
                    missingness,
                    signal_strength,
                )
                recommendations.append(
                    recommendation_record(
                        "Operational gap needs coverage planning",
                        (
                            f"Average `{workload_column}` exceeds `{staffing_column}` by "
                            f"{mean_gap:.1f}{readiness_clause}, indicating the operating "
                            "buffer may be under pressure."
                        ),
                        (
                            "Prepare surge support or reassignment for the highest-load "
                            "segments and set a simple escalation rule when the workload-to-"
                            "staffing gap stays above the recent norm."
                        ),
                        confidence,
                        evidence=(
                            f"Evaluated {len(operations):,} rows with both workload and staffing values."
                        ),
                        priority=signal_strength,
                    )
                )

    date_column, metric_column = best_trend_columns(
        data,
        numeric,
        dates,
    )
    quality_fields.extend(
        [
            column
            for column in (date_column, metric_column)
            if column
        ]
    )

    if date_column and metric_column:
        trend = pd.DataFrame(
            {
                "Date": parse_dates(data[date_column]),
                "Value": pd.to_numeric(
                    data[metric_column],
                    errors="coerce",
                ),
            }
        ).dropna().sort_values("Date")

        if len(trend) >= 10:
            trend = (
                trend.groupby("Date", as_index=False)
                .mean(numeric_only=True)
                .sort_values("Date")
            )
            window = max(4, min(10, len(trend) // 3))

            if len(trend) >= window * 2:
                baseline = trend.head(window)["Value"].mean()
                recent = trend.tail(window)["Value"].mean()
                scale = max(abs(baseline), 1.0)
                delta = (recent - baseline) / scale
                direction = metric_direction(metric_column)
                signal_strength = abs(delta)
                missingness = 1 - (
                    len(trend) / max(len(data), 1)
                )

                if signal_strength >= .12:
                    if (
                        direction == "higher_is_worse"
                        and delta > 0
                    ) or (
                        direction == "higher_is_better"
                        and delta < 0
                    ):
                        title = "Recent trend shows deterioration"
                        action = (
                            "Trigger a short-horizon mitigation review, check what changed "
                            "in the most recent period, and monitor this metric until it "
                            "moves back toward baseline."
                        )
                    elif (
                        direction == "higher_is_worse"
                        and delta < 0
                    ) or (
                        direction == "higher_is_better"
                        and delta > 0
                    ):
                        title = "Recent trend is improving"
                        action = (
                            "Sustain the current operating pattern, capture what changed in "
                            "the stronger period, and standardize it where similar segments "
                            "show the same conditions."
                        )
                    else:
                        title = "Recent trend moved materially"
                        action = (
                            "Use this as a monitoring signal, but verify whether higher or "
                            "lower values are desirable for this metric before changing "
                            "operations."
                        )

                    confidence = confidence_label(
                        len(trend),
                        missingness,
                        signal_strength,
                    )
                    recommendations.append(
                        recommendation_record(
                            title,
                            (
                                f"`{metric_column}` moved from a baseline average of "
                                f"{baseline:.1f} to a recent average of {recent:.1f} across "
                                f"`{date_column}`."
                            ),
                            action,
                            confidence,
                            evidence=(
                                f"Compared the earliest {window} periods with the latest {window} periods."
                            ),
                            priority=signal_strength,
                        )
                    )

    quality_fields = [
        column
        for column in dict.fromkeys(quality_fields)
        if column in data.columns
    ]
    if quality_fields:
        quality_missingness = (
            data[quality_fields].isna().mean().sort_values(ascending=False)
        )
        if (
            len(quality_missingness)
            and (
                quality_missingness.iloc[0] >= .3
                or quality_missingness.mean() >= .2
            )
        ):
            worst_field = quality_missingness.index[0]
            worst_rate = quality_missingness.iloc[0]
            confidence = confidence_label(
                row_count,
                float(quality_missingness.mean()),
                worst_rate,
            )
            recommendations.append(
                recommendation_record(
                    "Data quality should be tightened first",
                    (
                        f"`{worst_field}` is missing in {worst_rate:.1%} of the key fields "
                        "used for recommendations, so the current guidance should be treated "
                        "as directional rather than definitive."
                    ),
                    (
                        "Improve source capture or backfill the highest-missing operational "
                        "fields before making major staffing, readiness, or segment-level decisions."
                    ),
                    confidence,
                    evidence=(
                        f"Average missingness across key recommendation fields is {quality_missingness.mean():.1%}."
                    ),
                    priority=worst_rate,
                )
            )

    if not recommendations:
        fallback_confidence = confidence_label(
            row_count,
            float(data.isna().mean().mean()),
            .08,
        )
        recommendations.append(
            recommendation_record(
                "No strong recommendation signal yet",
                "This filtered slice does not show a stable concentration, operating gap, or directional trend large enough to justify a stronger action call.",
                "Use the chart and filter controls to inspect smaller cohorts or narrower time windows for localized issues before changing operations.",
                fallback_confidence,
                priority=.08,
            )
        )

    return [
        {
            key: value
            for key, value in recommendation.items()
            if not key.startswith("_")
        }
        for recommendation in sorted(
            recommendations,
            key=lambda item: (
                {"High": 2, "Medium": 1, "Low": 0}.get(
                    item["confidence"],
                    0,
                ),
                item.get("_priority", 0),
            ),
            reverse=True,
        )[:4]
    ]


def chart_for(
    data,
    numeric,
    dates,
    categorical,
    chart_type="Auto",
    x_column=None,
    y_column=None,
):
    category = (
        x_column
        if x_column in data.columns
        else best_category(data, categorical)
    )
    metric = (
        y_column
        if y_column in data.columns
        else (numeric[0] if numeric else None)
    )

    def fallback_count(reason):
        if (
            "Source file" in data.columns
            and data["Source file"].nunique(dropna=True) > 1
        ):
            source_counts = (
                clean_label(data["Source file"])
                .value_counts()
                .sort_values()
            )

            return (
                px.bar(
                    source_counts,
                    x=source_counts.values,
                    y=source_counts.index,
                    orientation="h",
                    title="Record count by source file",
                    color_discrete_sequence=["#a855f7"],
                ),
                f"{reason} Showing counts by source file instead.",
            )

        summary = pd.DataFrame(
            {
                "Metric": ["Records", "Fields"],
                "Value": [len(data), len(data.columns)],
            }
        )

        return (
            px.bar(
                summary,
                x="Metric",
                y="Value",
                title="Filtered dataset summary",
                color="Metric",
                color_discrete_map={
                    "Records": "#06b6d4",
                    "Fields": "#a855f7",
                },
            ),
            f"{reason} Showing a dataset summary instead.",
        )

    if chart_type == "Auto":
        for candidate, is_possible in [
            ("Bar", bool(category)),
            ("Line", bool(dates and metric)),
            ("Scatter", len(numeric) >= 2),
            ("Histogram", bool(metric)),
        ]:
            if not is_possible:
                continue

            chart, note = chart_for(
                data,
                numeric,
                dates,
                categorical,
                candidate,
                x_column,
                y_column,
            )
            if "unavailable for this schema" not in note:
                return chart, note

        return fallback_count(
            "Auto view was unavailable for this schema."
        )

    if chart_type == "Bar" and category:
        counts = (
            clean_label(data[category])
            .value_counts()
            .head(12)
            .sort_values()
        )

        if len(counts):
            return (
                px.bar(
                    counts,
                    x=counts.values,
                    y=counts.index,
                    orientation="h",
                    title=f"Composition by {category}",
                    color_discrete_sequence=["#a855f7"],
                ),
                f"Top segments in {category}",
            )

    if chart_type == "Line" and dates and metric:
        date_column = (
            x_column if x_column in dates else dates[0]
        )
        frame = pd.DataFrame(
            {
                "Date": parse_dates(data[date_column]),
                "Value": pd.to_numeric(
                    data[metric],
                    errors="coerce",
                ),
            }
        ).dropna().sort_values("Date")

        if len(frame):
            trend = (
                frame.set_index("Date")
                .resample("W")
                .mean(numeric_only=True)
                .dropna()
                .reset_index()
            )
            daily = (
                frame.groupby("Date", as_index=False)
                .mean(numeric_only=True)
                .sort_values("Date")
            )
            chart_frame = trend if len(trend) >= 3 else daily

            return (
                px.line(
                    chart_frame,
                    x="Date",
                    y="Value",
                    markers=True,
                    title=f"{metric} over {date_column}",
                    color_discrete_sequence=["#06b6d4"],
                ),
                "Time trend from one date and one numeric field",
            )

    if chart_type == "Scatter" and len(numeric) >= 2:
        x = x_column if x_column in numeric else numeric[0]
        y = y_column if y_column in numeric else numeric[1]
        if x == y:
            alternatives = [column for column in numeric if column != x]
            if alternatives:
                y = alternatives[0]

        frame = pd.DataFrame(
            {
                x: pd.to_numeric(data[x], errors="coerce"),
                y: pd.to_numeric(data[y], errors="coerce"),
            }
        ).dropna()

        if len(frame):
            return (
                px.scatter(
                    frame,
                    x=x,
                    y=y,
                    title=f"{x} vs {y}",
                    color_discrete_sequence=["#ec4899"],
                ),
                "Relationship between two numeric fields",
            )

    if chart_type == "Histogram" and metric:
        metric_values = pd.to_numeric(
            data[metric],
            errors="coerce",
        ).dropna()

        if len(metric_values):
            frame = pd.DataFrame({metric: metric_values})
            return (
                px.histogram(
                    frame,
                    x=metric,
                    nbins=20,
                    title=f"Distribution of {metric}",
                    color_discrete_sequence=["#06b6d4"],
                ),
                f"Distribution of {metric}",
            )

    if chart_type == "Quality":
        missing = data.isna().mean().sort_values().tail(12).sort_values()
        if not len(missing) or missing.max() <= 0:
            return fallback_count(
                "Quality view was unavailable for this schema."
            )
        return (
            px.bar(
                x=missing.values,
                y=missing.index,
                orientation="h",
                range_x=[0, 1],
                title="Data quality: missing values",
                color_discrete_sequence=["#f43f5e"],
            ),
            "Missingness by field",
        )

    if chart_type in {"Count", "Bar", "Line", "Scatter", "Histogram"}:
        return fallback_count(
            f"{chart_type} view was unavailable for this schema."
        )

    return fallback_count(
        f"{chart_type} view could not be built from the current fields."
    )


def charts_for(data, numeric, dates, categorical):
    charts = []
    fallback_signatures = set()

    choices = [
        ("Bar", None, None),
        (
            "Line",
            dates[0] if dates else None,
            numeric[0] if numeric else None,
        ),
        (
            "Scatter",
            numeric[0] if numeric else None,
            numeric[1] if len(numeric) > 1 else None,
        ),
        (
            "Histogram",
            None,
            numeric[0] if numeric else None,
        ),
    ]

    def alternate_fallback(kind):
        if kind == "Line" and len(data):
            sequence = pd.DataFrame(
                {
                    "Row": np.arange(1, len(data) + 1),
                    "Cumulative records": np.arange(1, len(data) + 1),
                }
            )
            return (
                px.line(
                    sequence,
                    x="Row",
                    y="Cumulative records",
                    title="Cumulative record sequence",
                    color_discrete_sequence=["#06b6d4"],
                ),
                "Fallback trend when no date/metric pair is available.",
            )

        cardinality = (
            data.nunique(dropna=True)
            .sort_values(ascending=False)
            .head(12)
        )
        if len(cardinality):
            frame = pd.DataFrame(
                {
                    "Field": cardinality.index.astype(str),
                    "Distinct values": cardinality.values,
                }
            )
            if kind == "Scatter":
                return (
                    px.scatter(
                        frame,
                        x="Field",
                        y="Distinct values",
                        title="Field cardinality snapshot",
                        color_discrete_sequence=["#ec4899"],
                    ),
                    "Distinct-value comparison across fields.",
                )
            return (
                px.bar(
                    frame.sort_values("Distinct values"),
                    x="Distinct values",
                    y="Field",
                    orientation="h",
                    title="Distinct values by field",
                    color_discrete_sequence=["#a855f7"],
                ),
                "Fallback schema summary across available fields.",
            )

        return chart_for(
            data,
            numeric,
            dates,
            categorical,
            "Count",
        )

    for kind, x, y in choices:
        chart, explanation = chart_for(
            data,
            numeric,
            dates,
            categorical,
            kind,
            x,
            y,
        )

        is_fallback = "instead." in explanation
        if is_fallback and explanation in fallback_signatures:
            chart, explanation = alternate_fallback(kind)
            is_fallback = "instead." in explanation
        if is_fallback:
            fallback_signatures.add(explanation)

        charts.append((chart, explanation))

    return charts


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


def format_recommendations(recommendations, limit=3):
    lines = []

    for recommendation in recommendations[:limit]:
        evidence = (
            f" Evidence: {recommendation['evidence']}"
            if recommendation.get("evidence")
            else ""
        )
        lines.append(
            "- "
            f"**{recommendation['title']}** "
            f"({recommendation['confidence']}) — "
            f"{recommendation['insight']} "
            f"**Action:** {recommendation['action']}{evidence}"
        )

    return "\n".join(lines)


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


def local_answer(question, data, numeric, dates, categorical, text):
    q = question.lower().strip()
    category = best_category(data, categorical)
    recommendation_intents = (
        "recommend",
        "action",
        "next step",
        "what should we do",
        "what do we do",
        "priority",
        "plan",
    )

    if data.empty:
        return (
            "The current filters return no rows, so there is nothing reliable to "
            "summarize or recommend yet."
        )

    if any(intent in q for intent in recommendation_intents):
        return format_recommendations(
            recommend_actions(
                data,
                numeric,
                dates,
                categorical,
                text,
            )
        )

    if any(word in q for word in ("chart", "graph", "visual", "plot")):
        if "line" in q or "trend" in q:
            return (
                "Use the optional focused chart controls to choose Line, then select "
                "a date and numeric field."
            )

        if "scatter" in q or "relationship" in q:
            return "Use Scatter to compare two numeric fields."

        if "hist" in q or "distribution" in q:
            return "Use Histogram to inspect the distribution of one numeric field."

        return (
            "Use the optional focused chart controls below this chat to select "
            "a custom chart type and fields."
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
            f"Detected date fields: "
            f"{', '.join(dates) if dates else 'none'}."
        )

    if category and (
        "largest" in q
        or "most" in q
        or "category" in q
    ):
        counts = clean_label(data[category]).value_counts()

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
        "categories, numeric summaries, and chart choices using only this dataset."
    )


with st.sidebar:
    st.header("Upload your data")

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
    selected = {}

    filterable_categories = []
    for value in categorical:
        try:
            unique_count = clean_label(analysis_data[value]).nunique(
                dropna=True
            )
        except Exception:
            continue

        if 1 < unique_count <= 20:
            filterable_categories.append(value)

    for column in filterable_categories[:4]:

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


st.title("⚓ Strategic Insight Studio")

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
recommendations = recommend_actions(
    filtered,
    numeric,
    dates,
    categorical,
    text,
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


st.subheader("Recommended actions")
recommendation_columns = st.columns(2)

for index, recommendation in enumerate(recommendations[:4]):
    evidence = (
        f"<br><em>{html.escape(recommendation['evidence'])}</em>"
        if recommendation.get("evidence")
        else ""
    )
    recommendation_html = f"""
    <div class="recommendation-card">
        <strong>{html.escape(recommendation["title"])}</strong><br>
        {html.escape(recommendation["insight"])}<br><br>
        <strong>Suggested action:</strong> {html.escape(recommendation["action"])}
        {evidence}<br>
        <span class="recommendation-confidence">
            Confidence: {html.escape(recommendation["confidence"])}
        </span>
    </div>
    """

    with recommendation_columns[index % 2]:
        st.markdown(
            recommendation_html,
            unsafe_allow_html=True,
        )


with st.expander("Ask the local data assistant", expanded=True):
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
        "Ask about this data or request a chart change…"
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
            text,
        )

        st.session_state.chat_history.append(
            {
                "role": "assistant",
                "content": answer,
            }
        )

        st.rerun()


st.subheader("Four-chart overview")

with st.sidebar:
    st.subheader("Focused chart (optional)")

    show_focused_chart = st.checkbox(
        "Add a focused custom chart",
        value=False,
        help=(
            "The dashboard overview always shows four auto-selected visuals. "
            "Enable this to add one custom chart."
        ),
    )

    chart_type = None
    x_column = None
    y_column = None

    if show_focused_chart:
        chart_type = st.selectbox(
            "Chart type",
            [
                "Bar",
                "Line",
                "Scatter",
                "Histogram",
                "Quality",
            ],
            help="Each chart uses at most one or two fields to stay readable.",
        )

        if chart_type == "Scatter":
            x_candidates = numeric
        elif chart_type == "Line":
            x_candidates = dates + categorical
        else:
            x_candidates = categorical + dates

        x_field_options = []
        for field in x_candidates:
            if field not in x_field_options:
                x_field_options.append(field)

        x_column = st.selectbox(
            "Category / X field",
            x_field_options + ["None"],
        )

        y_column = st.selectbox(
            "Numeric / Y field",
            numeric + ["None"],
        )

        x_column = None if x_column == "None" else x_column
        y_column = None if y_column == "None" else y_column


charts = charts_for(
    filtered,
    numeric,
    dates,
    categorical,
)

custom_view = None
if show_focused_chart and chart_type:
    custom_view = chart_for(
        filtered,
        numeric,
        dates,
        categorical,
        chart_type,
        x_column,
        y_column,
    )


dashboard_columns = st.columns(2)

for index, (chart, explanation) in enumerate(charts):
    chart.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(21,29,63,.3)",
        font=dict(color="#f0f9ff"),
        legend=dict(font=dict(color="#f0f9ff")),
        margin=dict(l=20, r=20, t=55, b=20),
    )

    column = dashboard_columns[index % 2]
    with column:
        st.plotly_chart(
            chart,
            use_container_width=True,
        )
        st.caption(explanation)


if custom_view:
    st.subheader("Focused custom chart")
    focused_chart, focused_note = custom_view
    focused_chart.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(21,29,63,.3)",
        font=dict(color="#f0f9ff"),
        legend=dict(font=dict(color="#f0f9ff")),
        margin=dict(l=20, r=20, t=55, b=20),
    )
    st.plotly_chart(
        focused_chart,
        use_container_width=True,
    )
    st.caption(f"Focused chart: {focused_note}")


with st.expander("Attention queue and prepared data"):
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
        "Download prepared view",
        prepared.to_csv(index=False).encode("utf-8"),
        "strategic_analysis_data.csv",
        "text/csv",
    )


if not using_demo:
    st.caption(
        "No-BS rule: charts identify patterns; verify underlying records "
        "before operational decisions."
    )
