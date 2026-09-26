import html
from io import BytesIO
from pathlib import Path
import re

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="SMOM | Predictive Insight Studio",
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
[data-testid="stFileUploaderDropzone"] { background:rgba(15,21,51,.78); border:1px solid var(--cyan); }
[data-testid="stFileUploaderDropzone"] div { color:var(--text) !important; }
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
    "embark",
    "debark",
    "underway",
    "in port",
    "deployment",
    "tdy",
    "orders",
    "leave",
    "liberty",
    "pcs",
    "duty station",
    "voucher",
    "itinerary",
    "port call",
    "request",
    "created",
    "received",
    "distributed",
)

RECOMMENDATION_PATTERN = re.compile(
    r"\brecommend(?:ation|ed)?s?\b|"
    r"\bnext steps?\b|"
    r"\bwhat should we do\b|"
    r"\bwhat do we do\b|"
    r"\bwhat actions?\b|"
    r"\bactions? (?:should|do|to take|next)\b|"
    r"\baction plan\b|"
    r"\bplan of action\b|"
    r"\btop priority\b|"
    r"\bhighest priority\b|"
    r"\bmain priority\b|"
    r"\bwhat(?:'s| is) (?:our |the )?priority\b",
    re.I,
)

PLOTLY_CHART_CONFIG = {
    "displayModeBar": True,
    "displaylogo": False,
}

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


def apply_chart_layout(chart):
    title = {}
    if getattr(chart.layout, "title", None):
        title = chart.layout.title.to_plotly_json()

    title.update(
        {
            "x": 0.02,
            "xanchor": "left",
            "y": 0.96,
            "yanchor": "top",
            "pad": {"t": 12, "b": 0},
        }
    )

    chart.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(21,29,63,.3)",
        font=dict(color="#f0f9ff"),
        legend=dict(font=dict(color="#f0f9ff")),
        margin=dict(l=20, r=20, t=90, b=20),
        title=title,
    )

    return chart


def chart_series(data, column, numeric, dates, categorical):
    if column not in data.columns:
        return pd.Series(dtype=object)

    if column in numeric:
        return pd.to_numeric(
            data[column].astype(str).str.replace(",", "", regex=False),
            errors="coerce",
        )

    if column in dates:
        return parse_dates(data[column], column)

    if column in categorical:
        return clean_label(data[column])

    return data[column]


def build_chart_working_copy(data, numeric, categorical):
    chart_data = data.copy()
    filled_columns = set()

    for column in numeric:
        if column not in chart_data.columns:
            continue

        numeric_values = pd.to_numeric(
            chart_data[column].astype(str).str.replace(",", "", regex=False),
            errors="coerce",
        )

        if numeric_values.notna().any():
            filled_values = (
                numeric_values.interpolate(
                    method="linear",
                    limit_direction="both",
                )
                .ffill()
                .bfill()
            )
        else:
            filled_values = numeric_values

        if filled_values.notna().sum() > numeric_values.notna().sum():
            filled_columns.add(column)

        chart_data[column] = filled_values

    for column in categorical:
        if column not in chart_data.columns:
            continue

        normalized = chart_data[column].replace({"": np.nan})
        non_null = normalized.dropna()
        if non_null.empty:
            continue

        mode = non_null.mode(dropna=True)
        fill_value = mode.iloc[0] if not mode.empty else non_null.iloc[0]
        filled_values = normalized.fillna(fill_value)

        if filled_values.notna().sum() > normalized.notna().sum():
            filled_columns.add(column)

        chart_data[column] = filled_values

    return chart_data, filled_columns


def chart_uses_interpolation(columns, filled_columns):
    return bool(set(columns) & set(filled_columns))


def best_category(data, categorical):
    if not categorical:
        return None

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
        "unit",
        "command",
        "ship",
        "vessel",
        "hull",
        "port",
        "billet",
        "rate",
        "rank",
        "manning",
        "crew",
        "watch",
        "berthing",
        "tdy",
        "orders",
        "travel",
        "leave",
        "liberty",
        "pcs",
        "duty station",
        "itinerary",
        "deployment",
        "underway",
        "in port",
        "arrival",
        "departure",
        "employee",
        "type",
        "travel voucher",
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
        else categorical[0]
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


def maritime_context(data):
    names = " ".join(map(str, data.columns)).lower()
    return {
        "crew": any(
            word in names
            for word in (
                "billet",
                "rate",
                "rank",
                "manning",
                "crew",
                "watch",
                "berthing",
            )
        ),
        "travel": any(
            word in names
            for word in (
                "tdy",
                "orders",
                "leave",
                "liberty",
                "pcs",
                "duty station",
                "travel voucher",
                "travel",
                "per diem",
                "itinerary",
            )
        ),
        "port": any(
            word in names
            for word in (
                "vessel",
                "hull",
                "port",
                "embark",
                "debark",
                "deployment",
                "underway",
                "in port",
                "ship",
                "unit",
                "command",
            )
        ),
    }


def domain_terms(data):
    context = maritime_context(data)
    if context["crew"] and context["travel"]:
        return {
            "records": "crew and travel records",
            "segment": "crew/travel segment",
            "focus": "manning and TDY/travel operations",
        }
    if context["crew"]:
        return {
            "records": "billets",
            "segment": "crew segment",
            "focus": "manning operations",
        }
    if context["travel"]:
        return {
            "records": "travel requests",
            "segment": "travel segment",
            "focus": "TDY/travel execution",
        }
    if context["port"]:
        return {
            "records": "port movements",
            "segment": "port segment",
            "focus": "port operations",
        }
    return {
        "records": "records",
        "segment": "segment",
        "focus": "operations",
    }


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
    if sample_size < 10 or missingness >= .35:
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
        return "Medium" if missingness >= .2 else "High"

    if score >= 3:
        return "Medium"

    return "Low"


def prediction_readiness_components(data, numeric, dates, categorical):
    if data.empty:
        return {
            "readiness_score": 0.0,
            "coverage": 0.0,
            "schema_richness": 0.0,
            "trendability": 0.0,
            "signal_density": 0.0,
            "field_signal": pd.Series(dtype=float),
        }

    row_count = len(data)
    coverage = float(data.notna().mean().mean())
    schema_richness = min(1.0, len(data.columns) / 30)
    trendability = min(1.0, len(dates) / 2)
    signal_density = min(
        1.0,
        (len(numeric) + len(categorical)) / max(len(data.columns), 1),
    )

    readiness_score = (
        0.35 * coverage
        + 0.25 * schema_richness
        + 0.2 * trendability
        + 0.2 * signal_density
    )

    field_scores = {}
    for column in data.columns:
        non_null = data[column].dropna()
        coverage_score = float(data[column].notna().mean())
        if non_null.empty:
            uniqueness = 0.0
        else:
            uniqueness = min(1.0, non_null.nunique(dropna=True) / len(non_null))

        variability = 0.0
        if column in numeric:
            numeric_values = pd.to_numeric(data[column], errors="coerce").dropna()
            if len(numeric_values) > 1:
                denominator = max(abs(float(numeric_values.mean())), 1.0)
                variability = min(
                    1.0,
                    float(numeric_values.std()) / denominator,
                )

        field_scores[column] = (
            0.55 * coverage_score
            + 0.3 * uniqueness
            + 0.15 * variability
        )

    return {
        "readiness_score": readiness_score,
        "coverage": coverage,
        "schema_richness": schema_richness,
        "trendability": trendability,
        "signal_density": signal_density,
        "field_signal": pd.Series(field_scores).sort_values(ascending=False),
    }


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
    terms = domain_terms(data)
    maritime_mode = terms["records"] != "records"

    category = best_category(data, categorical)
    if category and category in data:
        quality_fields.append(category)
        counts = clean_label(data[category]).value_counts()

        if len(counts):
            top_label = counts.index[0]
            top_count = int(counts.iloc[0])
            top_share = top_count / row_count
            safe_top_label = escape_markdown(top_label)
            safe_category = escape_markdown(category)

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
                            f"`{safe_top_label}` accounts for {top_share:.1%} of the current "
                            f"`{safe_category}` volume, which suggests {terms['focus']} is concentrated "
                            f"in one {terms['segment']}."
                        ),
                        (
                            "Bias near-term capacity and review effort toward this segment, "
                            f"then split `{safe_top_label}` by time or other filters to confirm "
                            "which sub-cohort is driving the concentration."
                        ),
                        confidence,
                        evidence=(
                            f"{top_count:,} of {row_count:,} {terms['records']} fall into `{safe_top_label}`."
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
            threshold = max(2.0, abs(workload_mean) * .08)
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
                safe_workload_column = escape_markdown(workload_column)
                safe_staffing_column = escape_markdown(staffing_column)
                readiness_clause = (
                    f" and `{escape_markdown(readiness_column)}` averages {readiness_mean:.1f}"
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
                            f"Average `{safe_workload_column}` exceeds `{safe_staffing_column}` by "
                            f"{mean_gap:.1f}{readiness_clause}, indicating "
                            f"{'manning/travel' if maritime_mode else 'operating'} "
                            "buffer may be under pressure."
                        ),
                        (
                            (
                                "Prepare surge support or reassignment for the highest-load crew/travel "
                                "segments and set a simple escalation rule when the workload-to-staffing "
                                "gap stays above the recent norm."
                                if maritime_mode
                                else "Prepare surge support or reassignment for the highest-load "
                                "segments and set a simple escalation rule when the workload-to-"
                                "staffing gap stays above the recent norm."
                            )
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
        raw_trend = pd.DataFrame(
            {
                "Date": parse_dates(data[date_column]),
                "Value": pd.to_numeric(
                    data[metric_column],
                    errors="coerce",
                ),
            }
        ).dropna().sort_values("Date")
        raw_trend["Date"] = raw_trend["Date"].dt.normalize()
        trend_coverage = len(raw_trend) / max(len(data), 1)
        trend = raw_trend

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
                missingness = 1 - trend_coverage

                if signal_strength >= .12:
                    safe_metric_column = escape_markdown(metric_column)
                    safe_date_column = escape_markdown(date_column)
                    if (
                        direction == "higher_is_worse"
                        and delta > 0
                    ) or (
                        direction == "higher_is_better"
                        and delta < 0
                    ):
                        title = "Recent trend shows deterioration"
                        action = (
                            (
                                "Trigger a short-horizon trend review, check what changed in the "
                                "most recent watch/port/travel period, and monitor this metric until "
                                "it moves back toward baseline."
                                if maritime_mode
                                else "Trigger a short-horizon mitigation review, check what changed "
                                "in the most recent period, and monitor this metric until it "
                                "moves back toward baseline."
                            )
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
                            (
                                "Sustain the current operating pattern, capture what changed in the "
                                "stronger period, and standardize it where similar billets, crews, "
                                "or travel queues show the same conditions."
                                if maritime_mode
                                else "Sustain the current operating pattern, capture what changed in "
                                "the stronger period, and standardize it where similar segments "
                                "show the same conditions."
                            )
                        )
                    else:
                        title = "Recent trend moved materially"
                        action = (
                            (
                                "Use this as a monitoring signal, but verify whether higher or lower "
                                "values are desirable for this metric before changing manning/travel "
                                "operations."
                                if maritime_mode
                                else "Use this as a monitoring signal, but verify whether higher or "
                                "lower values are desirable for this metric before changing "
                                "operations."
                            )
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
                                f"`{safe_metric_column}` moved from a baseline average of "
                                f"{baseline:.1f} to a recent average of {recent:.1f} across "
                                f"`{safe_date_column}`."
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
        profile = prediction_readiness_components(
            data[quality_fields],
            [column for column in numeric if column in quality_fields],
            [column for column in dates if column in quality_fields],
            [column for column in categorical if column in quality_fields],
        )
        low_signal = profile["field_signal"].sort_values().head(1)
        if len(low_signal) and float(low_signal.iloc[0]) < .45:
            weakest_field = low_signal.index[0]
            weakest_score = float(low_signal.iloc[0])
            confidence = confidence_label(
                row_count,
                1 - profile["coverage"],
                .45 - weakest_score,
            )
            recommendations.append(
                recommendation_record(
                    "Strengthen weak feature signals",
                    (
                        f"`{escape_markdown(weakest_field)}` has a low signal score "
                        f"({weakest_score:.2f}) compared with other key fields."
                    ),
                    (
                        "Improve collection consistency and feature detail for weak-signal "
                        "fields before acting on predictive comparisons."
                    ),
                    confidence,
                    evidence=(
                        f"Key-field coverage is {profile['coverage']:.1%} with schema richness "
                        f"{profile['schema_richness']:.1%}."
                    ),
                    priority=.45 - weakest_score,
                )
            )

    if not recommendations:
        fallback_confidence = confidence_label(
            row_count,
            1 - float(data.notna().mean().mean()),
            .08,
        )
        recommendations.append(
            recommendation_record(
                "No strong recommendation signal yet",
                "This filtered slice does not show a stable concentration, operating gap, or directional trend large enough to justify a stronger action call.",
                (
                    "Use the chart and filter controls to inspect smaller cohorts or narrower time windows for localized predictive signals before changing operations."
                    if maritime_mode
                    else "Use the chart and filter controls to inspect smaller cohorts or narrower time windows for localized predictive signals before changing operations."
                ),
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


@st.cache_data(show_spinner=False)
def cached_recommend_actions(
    data,
    numeric,
    dates,
    categorical,
    text,
):
    return recommend_actions(
        data,
        list(numeric),
        list(dates),
        list(categorical),
        list(text),
    )


def chart_for(
    data,
    numeric,
    dates,
    categorical,
    chart_type="Auto",
    x_column=None,
    y_column=None,
):
    numeric_cache = {}
    date_cache = {}

    def numeric_values(column):
        if column not in numeric_cache:
            numeric_cache[column] = pd.to_numeric(
                data[column].astype(str).str.replace(",", "", regex=False),
                errors="coerce",
            )
        return numeric_cache[column]

    def parsed_dates(column):
        if column not in date_cache:
            date_cache[column] = parse_dates(data[column])
        return date_cache[column]

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
                ["Source file"],
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
            [],
        )

    def best_metric_column():
        candidates = []
        for column in numeric:
            values = numeric_values(column)
            candidates.append(
                (
                    values.notna().mean(),
                    values.std(skipna=True) > 0,
                    values.nunique(dropna=True),
                    column,
                )
            )
        return max(candidates)[-1] if candidates else metric

    if y_column in numeric and y_column in data.columns:
        metric = y_column
    else:
        metric = best_metric_column()

    if chart_type == "Auto":
        for candidate, is_possible in [
            ("Bar", bool(category)),
            ("Line", bool(dates and metric)),
            ("Scatter", len(numeric) >= 2),
            ("Histogram", bool(metric)),
        ]:
            if not is_possible:
                continue

            chart, note, relevant_columns = chart_for(
                data,
                numeric,
                dates,
                categorical,
                candidate,
                x_column,
                y_column,
            )
            if "unavailable for this schema" not in note:
                return chart, note, relevant_columns

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
                [category],
            )

    if chart_type == "Line" and dates and metric:
        date_column = (
            x_column if x_column in dates else dates[0]
        )
        frame = pd.DataFrame(
            {
                "Date": parsed_dates(date_column),
                "Value": numeric_values(metric),
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
                [date_column, metric],
            )

    if chart_type == "Scatter" and len(numeric) >= 2:
        def pair_viability(left, right):
            overlap = pd.concat(
                [numeric_values(left), numeric_values(right)],
                axis=1,
            ).dropna()
            return (
                len(overlap),
                overlap.iloc[:, 0].std(skipna=True) > 0,
                overlap.iloc[:, 1].std(skipna=True) > 0,
            )

        pair_candidates = []
        for index, left in enumerate(numeric):
            for right in numeric[index + 1 :]:
                overlap_len, left_varies, right_varies = pair_viability(left, right)
                if overlap_len < 5 or not (left_varies and right_varies):
                    continue
                pair_candidates.append(
                    (
                        overlap_len,
                        left,
                        right,
                    )
                )

        explicit_viable = False
        if x_column in numeric and y_column in numeric and x_column != y_column:
            overlap_len, left_varies, right_varies = pair_viability(
                x_column,
                y_column,
            )
            explicit_viable = (
                overlap_len >= 5
                and left_varies
                and right_varies
            )

        if explicit_viable:
            x, y = x_column, y_column
        elif pair_candidates:
            _, x, y = max(pair_candidates)
        else:
            x, y = numeric[0], numeric[1]

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
                [x, y],
            )

    if chart_type == "Box" and metric and category:
        frame = pd.DataFrame(
            {
                "Category": clean_label(data[category]),
                metric: numeric_values(metric),
            }
        ).dropna()

        if len(frame):
            category_order = (
                frame["Category"]
                .value_counts()
                .head(8)
                .index
                .tolist()
            )
            frame = frame[frame["Category"].isin(category_order)]
            if len(frame):
                return (
                    px.box(
                        frame,
                        x="Category",
                        y=metric,
                        title=f"{metric} variation by {category}",
                        color_discrete_sequence=["#ec4899"],
                    ),
                    "Distribution spread by category",
                    [category, metric],
                )

    if chart_type == "CountTimeline" and dates:
        date_column = x_column if x_column in dates else dates[0]
        frame = pd.DataFrame(
            {
                "Date": parsed_dates(date_column),
            }
        ).dropna().copy()
        if len(frame):
            if frame["Date"].dt.normalize().nunique() < frame["Date"].nunique():
                span_days = (
                    frame["Date"].max() - frame["Date"].min()
                ).days
                if span_days > 60:
                    frame["Date"] = frame["Date"].dt.floor("D")
                elif span_days > 2:
                    frame["Date"] = frame["Date"].dt.floor("H")
                else:
                    frame["Date"] = frame["Date"].dt.floor("15min")
            trend = (
                frame.groupby("Date", as_index=False)
                .size()
                .rename(columns={"size": "Records"})
                .sort_values("Date")
            )
            if len(trend):
                return (
                    px.line(
                        trend,
                        x="Date",
                        y="Records",
                        markers=True,
                        title=f"Record volume over {date_column}",
                        color_discrete_sequence=["#06b6d4"],
                    ),
                    "Record-volume trend across the detected time field",
                    [date_column],
                )

    if chart_type == "Histogram" and metric:
        metric_values = numeric_values(metric).dropna()

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
                [metric],
            )

    if chart_type == "Signal":
        profile = prediction_readiness_components(data, numeric, dates, categorical)
        field_signal = (
            profile["field_signal"]
            .sort_values(ascending=False)
            .head(12)
            .sort_values()
        )
        if not len(field_signal):
            return fallback_count(
                "Signal view was unavailable for this schema."
            )
        return (
            px.bar(
                x=field_signal.values,
                y=field_signal.index,
                orientation="h",
                range_x=[0, 1],
                title="Feature signal strength by field",
                color_discrete_sequence=["#f43f5e"],
            ),
            "Relative signal strength by field",
            [column for column in numeric + categorical if column in data.columns],
        )

    if chart_type in {"Count", "Bar", "Line", "Scatter", "Histogram", "Box", "CountTimeline"}:
        return fallback_count(
            f"{chart_type} view was unavailable for this schema."
        )

    return fallback_count(
        f"{chart_type} view could not be built from the current fields."
    )


def charts_for(data, numeric, dates, categorical):
    charts = []
    fallback_signatures = set()
    preferred_numeric = None

    choices = [
        ["Bar", "Histogram", "Count"],
        ["Line", "CountTimeline", "Bar", "Count"],
        ["Scatter", "Box", "Bar", "Count"],
        ["Histogram", "Box", "Bar", "Count"],
    ]

    if numeric:
        metric_candidates = []
        for column in numeric:
            values = pd.to_numeric(data[column], errors="coerce")
            metric_candidates.append(
                (
                    values.notna().mean(),
                    values.std(skipna=True) > 0,
                    values.nunique(dropna=True),
                    column,
                )
            )
        preferred_numeric = max(metric_candidates)[-1]

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
                [],
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
                    frame["Field"].tolist(),
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
                frame["Field"].tolist(),
            )

        return chart_for(
            data,
            numeric,
            dates,
            categorical,
            "Count",
        )

    def default_axes(kind):
        if kind in {"Line", "CountTimeline"}:
            return dates[0] if dates else None, preferred_numeric
        if kind == "Scatter":
            return (
                numeric[0] if numeric else None,
                numeric[1] if len(numeric) > 1 else None,
            )
        if kind == "Box":
            return (
                best_category(data, categorical),
                preferred_numeric,
            )
        if kind == "Histogram":
            return None, preferred_numeric
        if kind == "Bar":
            return best_category(data, categorical), None
        return None, None

    for slot_kinds in choices:
        chart = None
        explanation = ""
        relevant_columns = []
        for kind in slot_kinds:
            x_default, y_default = default_axes(kind)
            chart, explanation, relevant_columns = chart_for(
                data,
                numeric,
                dates,
                categorical,
                kind,
                x_default,
                y_default,
            )
            if (
                "unavailable for this schema" not in explanation
                and "instead." not in explanation
            ):
                break

        is_fallback = (
            "instead." in explanation
            or "unavailable for this schema" in explanation
        )
        if is_fallback and explanation in fallback_signatures:
            chart, explanation, relevant_columns = alternate_fallback(slot_kinds[0])
            is_fallback = (
                "instead." in explanation
                or "unavailable for this schema" in explanation
            )
        if is_fallback:
            fallback_signatures.add(explanation)

        charts.append((chart, explanation, relevant_columns))

    return charts


def build_custom_chart(
    data,
    numeric,
    dates,
    categorical,
    chart_type,
    x_column,
    y_column=None,
    color_column=None,
    facet_column=None,
    size_column=None,
):
    if x_column not in data.columns:
        return None, "Select a valid X-axis column.", []

    y_required = chart_type != "Histogram"
    if y_required and y_column not in data.columns:
        return None, "Select a valid Y-axis column to render this chart.", [x_column]

    if chart_type in {"Scatter", "Histogram"} and x_column not in numeric:
        return None, f"`{x_column}` must be numeric for a {chart_type.lower()} chart.", [x_column]

    if chart_type in {"Bar", "Line", "Box", "Area"} and y_column not in numeric:
        return None, f"`{y_column}` must be numeric for a {chart_type.lower()} chart.", [x_column, y_column]

    if chart_type == "Scatter" and y_column not in numeric:
        return None, f"`{y_column}` must be numeric for a scatter chart.", [x_column, y_column]

    relevant_columns = [
        column
        for column in (x_column, y_column, color_column, facet_column, size_column)
        if column in data.columns
    ]
    frame = pd.DataFrame(index=data.index)
    frame["X"] = chart_series(data, x_column, numeric, dates, categorical)

    required = ["X"]
    if y_required:
        frame["Y"] = chart_series(data, y_column, numeric, dates, categorical)
        required.append("Y")

    if color_column in data.columns:
        frame["Color"] = chart_series(data, color_column, numeric, dates, categorical)

    if facet_column in data.columns:
        frame["Facet"] = chart_series(data, facet_column, numeric, dates, categorical)

    if size_column in data.columns:
        frame["Size"] = chart_series(data, size_column, numeric, dates, categorical)

    frame = frame.dropna(subset=required)

    minimum_rows = 5 if chart_type in {"Line", "Scatter", "Area"} else 2
    if len(frame) < minimum_rows:
        return (
            None,
            "Not enough overlapping data between selected columns to render this chart.",
            relevant_columns,
        )

    if chart_type == "Scatter":
        if frame["X"].nunique(dropna=True) < 2 or frame["Y"].nunique(dropna=True) < 2:
            return (
                None,
                "Not enough overlapping data between selected columns to render this chart.",
                relevant_columns,
            )
        return (
            px.scatter(
                frame,
                x="X",
                y="Y",
                color="Color" if "Color" in frame else None,
                facet_col="Facet" if "Facet" in frame else None,
                size="Size" if "Size" in frame else None,
                title=f"{x_column} vs {y_column}",
                color_discrete_sequence=["#ec4899"],
            ),
            f"Custom scatter using `{x_column}` and `{y_column}`.",
            relevant_columns,
        )

    if chart_type == "Histogram":
        if frame["X"].nunique(dropna=True) < 1:
            return (
                None,
                "Not enough overlapping data between selected columns to render this chart.",
                relevant_columns,
            )
        return (
            px.histogram(
                frame,
                x="X",
                color="Color" if "Color" in frame else None,
                facet_col="Facet" if "Facet" in frame else None,
                nbins=20,
                title=f"Distribution of {x_column}",
                color_discrete_sequence=["#06b6d4"],
            ),
            f"Custom histogram using `{x_column}`.",
            relevant_columns,
        )

    aggregate = frame.copy()
    if x_column in dates:
        aggregate["X"] = aggregate["X"].dt.normalize()

    if chart_type in {"Bar", "Line", "Area"}:
        group_fields = ["X"]
        if "Color" in aggregate:
            group_fields.append("Color")
        if "Facet" in aggregate:
            group_fields.append("Facet")

        aggregate = (
            aggregate.groupby(group_fields, dropna=False, as_index=False)["Y"]
            .mean()
        )

        if x_column in dates:
            aggregate = aggregate.sort_values("X")
        elif chart_type == "Bar":
            aggregate = aggregate.sort_values("Y", ascending=False).head(20)

        common_kwargs = {
            "data_frame": aggregate,
            "x": "X",
            "y": "Y",
            "color": "Color" if "Color" in aggregate else None,
            "facet_col": "Facet" if "Facet" in aggregate else None,
            "title": f"{y_column} by {x_column}",
            "color_discrete_sequence": ["#06b6d4", "#a855f7", "#ec4899"],
        }

        if chart_type == "Bar":
            figure = px.bar(**common_kwargs)
        elif chart_type == "Line":
            figure = px.line(
                **common_kwargs,
                markers=True,
            )
        else:
            figure = px.area(**common_kwargs)

        return (
            figure,
            f"Custom {chart_type.lower()} using `{x_column}` and `{y_column}`.",
            relevant_columns,
        )

    if chart_type == "Box":
        return (
            px.box(
                frame,
                x="X",
                y="Y",
                color="Color" if "Color" in frame else None,
                facet_col="Facet" if "Facet" in frame else None,
                title=f"{y_column} variation by {x_column}",
                color_discrete_sequence=["#ec4899", "#06b6d4", "#a855f7"],
            ),
            f"Custom box plot using `{x_column}` and `{y_column}`.",
            relevant_columns,
        )

    return None, f"{chart_type} is not supported in the custom builder yet.", relevant_columns


def insights(data, numeric, dates, categorical, text):
    findings = []
    terms = domain_terms(data)

    if categorical:
        category = best_category(data, categorical)
        counts = clean_label(data[category]).value_counts()

        if len(counts):
            findings.append(
                f"**{counts.index[0]}** is the largest `{category}` {terms['segment']} "
                f"at **{counts.iloc[0] / len(data):.1%}** of {terms['records']}."
            )

    if dates:
        parsed = parse_dates(data[dates[0]]).dropna()

        if len(parsed):
            findings.append(
                f"`{dates[0]}` spans "
                f"**{parsed.min():%Y-%m-%d} to {parsed.max():%Y-%m-%d}**."
            )

    profile = prediction_readiness_components(data, numeric, dates, categorical)
    field_signal = profile["field_signal"]
    if len(field_signal):
        findings.append(
            f"Prediction readiness is **{profile['readiness_score']:.0%}**, led by "
            f"**{field_signal.index[0]}** as the strongest feature signal."
        )

    return (
        " ".join(findings)
        or "Not enough structure for a directional finding; validate the source schema first."
    )


def escape_markdown(value):
    return re.sub(
        r"([\\`*_{}\[\]()#+\-=|>!])",
        r"\\\1",
        str(value).replace("\n", " "),
    )


def is_recommendation_request(question):
    return bool(
        RECOMMENDATION_PATTERN.search(str(question))
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


def local_answer(question, data, numeric, dates, categorical, text):
    q = question.lower().strip()
    category = best_category(data, categorical)
    terms = domain_terms(data)

    if data.empty:
        return (
            "The current filters return no rows, so there is nothing reliable to "
            + (
                "summarize for robust prediction insights yet."
                if terms["records"] != "records"
                else "summarize or recommend yet."
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
            "Use the focused chart controls or the Build your own chart section "
            "to select a custom chart type and fields."
        )

    if is_recommendation_request(q):
        return format_recommendations(
            cached_recommend_actions(
                data,
                tuple(numeric),
                tuple(dates),
                tuple(categorical),
                tuple(text),
            )
        )

    if any(
        phrase in q
        for phrase in (
            "manning gap",
            "travel backlog",
            "tdy backlog",
            "port readiness",
            "predictive signal",
        )
    ):
        return format_recommendations(
            cached_recommend_actions(
                data,
                tuple(numeric),
                tuple(dates),
                tuple(categorical),
                tuple(text),
            )
        )

    if "missing" in q:
        missing = data.isna().mean().sort_values(ascending=False).head(5)
        if len(missing):
            return "Top missing fields: " + "; ".join(
                f"{column} {value:.1%}"
                for column, value in missing.items()
            ) + "."
        return "No missing values were detected in the current filtered dataset."

    if "quality" in q:
        profile = prediction_readiness_components(data, numeric, dates, categorical)
        return (
            f"Prediction readiness is {profile['readiness_score']:.0%} "
            f"(coverage {profile['coverage']:.0%}, schema richness {profile['schema_richness']:.0%}, "
            f"trendability {profile['trendability']:.0%})."
        )

    if "how many" in q or "rows" in q or "records" in q:
        return (
            f"The current filtered dataset contains {len(data):,} {terms['records']} "
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
            f"The largest {category} {terms['segment']} is {counts.index[0]} with "
            f"{counts.iloc[0]:,} {terms['records']} "
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
        (
            "I can answer questions about counts, prediction readiness, date coverage, largest segments, recommendation priorities, and chart choices for this dataset."
            if terms["records"] != "records"
            else "I can answer questions about row counts, prediction readiness, detected dates, categories, numeric summaries, and chart choices using only this dataset."
        )
    )


with st.sidebar:
    st.header("Upload data")

    uploads = st.file_uploader(
        "Upload dataset files",
        type=SUPPORTED_TYPES,
        accept_multiple_files=True,
        help="CSV, Excel, JSON, Parquet, and XML are supported.",
    )

    st.caption(
        "Add one or more files. The dashboard auto-adapts its four core charts "
        "to the current dataset and filters."
    )
    st.caption("Everything runs locally in this session; no external data transfer.")


uploaded_data, errors = load_uploads(uploads)
analysis_data = uploaded_data

st.title("🔮 SMOM | Adaptive Insight Dashboard")

st.caption(
    "Upload your data to generate a local-only, adaptive four-chart overview "
    "plus assistant guidance based on the active filtered dataset."
)

for error in errors:
    st.warning(error)

if analysis_data.empty:
    st.info(
        "Upload any dataset to begin personalized signal discovery and predictive insights."
    )
    st.stop()

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

st.success(
    f"Analyzing {len(uploads)} file(s), "
    f"{len(filtered):,} filtered rows, and "
    f"{len(filtered.columns):,} fields."
)

readiness_profile = (
    prediction_readiness_components(filtered, numeric, dates, categorical)
    if not filtered.empty
    else {
        "readiness_score": 0.0,
        "coverage": 0.0,
        "schema_richness": 0.0,
        "trendability": 0.0,
        "signal_density": 0.0,
        "field_signal": pd.Series(dtype=float),
    }
)
recommendations = cached_recommend_actions(
    filtered,
    tuple(numeric),
    tuple(dates),
    tuple(categorical),
    tuple(text),
)

metrics = st.columns(4)

metrics[0].metric("RECORDS", f"{len(filtered):,}")
metrics[1].metric("FIELDS", f"{len(filtered.columns):,}")
metrics[2].metric(
    "DATE / NUMERIC SIGNALS",
    f"{len(dates)} / {len(numeric)}",
)
metrics[3].metric("PREDICTION READINESS", f"{readiness_profile['readiness_score']:.0%}")


st.markdown(
    f"""
<div class="insight">
<strong>
{"Strong predictive signal profile detected."
if readiness_profile["readiness_score"] >= .65
else "Signal profile is moderate; refine filters to strengthen predictions."}
</strong>
<br>
{insights(filtered, numeric, dates, categorical, text)}
</div>
""",
    unsafe_allow_html=True,
)


st.subheader("Adaptive four-chart overview")

with st.sidebar:
    st.subheader("Chart data options")
    fill_missing_for_charts = st.checkbox(
        "Fill missing data to improve chart options",
        value=False,
        help=(
            "Only chart rendering uses this working copy. Numeric fields are interpolated "
            "and categorical gaps use the most frequent value."
        ),
    )

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
                "Signal",
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


chart_data, chart_filled_columns = (
    build_chart_working_copy(filtered, numeric, categorical)
    if fill_missing_for_charts
    else (filtered.copy(), set())
)

charts = charts_for(
    chart_data,
    numeric,
    dates,
    categorical,
)

custom_view = None
if show_focused_chart and chart_type:
    custom_view = chart_for(
        chart_data,
        numeric,
        dates,
        categorical,
        chart_type,
        x_column,
        y_column,
    )


dashboard_columns = st.columns(2)

for index, (chart, explanation, relevant_columns) in enumerate(charts):
    apply_chart_layout(chart)
    column = dashboard_columns[index % 2]
    with column:
        st.plotly_chart(
            chart,
            width="stretch",
            config=PLOTLY_CHART_CONFIG,
            key=f"adaptive-chart-{index}",
        )
        st.caption(explanation)
        if fill_missing_for_charts and chart_uses_interpolation(
            relevant_columns,
            chart_filled_columns,
        ):
            st.caption("ℹ️ Interpolated data used for this chart.")


if custom_view:
    st.subheader("Focused custom chart")
    focused_chart, focused_note, focused_columns = custom_view
    apply_chart_layout(focused_chart)
    st.plotly_chart(
        focused_chart,
        width="stretch",
        config=PLOTLY_CHART_CONFIG,
        key="focused-custom-chart",
    )
    st.caption(f"Focused chart: {focused_note}")
    if fill_missing_for_charts and chart_uses_interpolation(
        focused_columns,
        chart_filled_columns,
    ):
        st.caption("ℹ️ Interpolated data used for this chart.")


st.subheader("Build your own chart")
st.caption(
    "Force the axes for an additional custom chart without changing the adaptive four-chart overview."
)

builder_chart_type = st.selectbox(
    "Chart type",
    ["Bar", "Line", "Scatter", "Box", "Histogram", "Area"],
    key="builder_chart_type",
)

if builder_chart_type == "Histogram":
    builder_x_options = numeric
elif builder_chart_type == "Scatter":
    builder_x_options = numeric
elif builder_chart_type in {"Line", "Area"}:
    builder_x_options = dates + categorical
elif builder_chart_type == "Box":
    builder_x_options = categorical + dates
else:
    builder_x_options = categorical + dates + text

builder_control_columns = st.columns(4)
builder_x_column = builder_control_columns[0].selectbox(
    "X-axis column",
    builder_x_options if builder_x_options else ["No compatible columns"],
    key="builder_x_column",
)

builder_y_column = None
if builder_chart_type != "Histogram":
    builder_y_options = numeric
    builder_y_column = builder_control_columns[1].selectbox(
        "Y-axis column",
        builder_y_options if builder_y_options else ["No compatible columns"],
        key="builder_y_column",
    )

color_options = [
    "None",
    *[
        column
        for column in categorical
        if column not in {builder_x_column, builder_y_column}
    ],
]
facet_options = [
    "None",
    *[
        column
        for column in categorical + dates
        if column not in {builder_x_column, builder_y_column}
    ],
]

builder_color_column = builder_control_columns[2].selectbox(
    "Color / group-by (optional)",
    color_options,
    key="builder_color_column",
)
builder_facet_column = builder_control_columns[3].selectbox(
    "Facet (optional)",
    facet_options,
    key="builder_facet_column",
)

builder_size_column = None
if builder_chart_type == "Scatter":
    size_options = [
        "None",
        *[
            column
            for column in numeric
            if column not in {builder_x_column, builder_y_column}
        ],
    ]
    builder_size_column = st.selectbox(
        "Size (optional)",
        size_options,
        key="builder_size_column",
    )

builder_invalid_selection = (
    not builder_x_options
    or builder_x_column == "No compatible columns"
    or (
        builder_chart_type != "Histogram"
        and (not numeric or builder_y_column == "No compatible columns")
    )
)

if builder_invalid_selection:
    st.warning("No compatible column combination is available for this chart type yet.")
else:
    builder_chart, builder_note, builder_columns = build_custom_chart(
        chart_data,
        numeric,
        dates,
        categorical,
        builder_chart_type,
        builder_x_column,
        builder_y_column,
        None if builder_color_column == "None" else builder_color_column,
        None if builder_facet_column == "None" else builder_facet_column,
        None if builder_size_column == "None" else builder_size_column,
    )

    if builder_chart is None:
        st.warning(builder_note)
    else:
        apply_chart_layout(builder_chart)
        st.plotly_chart(
            builder_chart,
            width="stretch",
            config=PLOTLY_CHART_CONFIG,
            key="builder-custom-chart",
        )
        st.caption(builder_note)
        if fill_missing_for_charts and chart_uses_interpolation(
            builder_columns,
            chart_filled_columns,
        ):
            st.caption("ℹ️ Interpolated data used for this chart.")


st.subheader("Assistant recommendations")
st.caption(
    "Follow-up guidance generated from the currently rendered charts and active filters."
)
st.markdown(
    f'<div class="insight"><strong>Current chart finding:</strong> {insights(filtered, numeric, dates, categorical, text)}</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div role="list" aria-label="Recommended actions">',
    unsafe_allow_html=True,
)

for recommendation in recommendations[:4]:
    recommendation_html = f"""
    <article class="recommendation-card" role="listitem">
        <h4>{html.escape(recommendation["title"])}</h4>
        <p><strong>Insight:</strong> {html.escape(recommendation["insight"])}</p>
        <p><strong>Suggested action:</strong> {html.escape(recommendation["action"])}</p>
        {f"<p><strong>Evidence:</strong> {html.escape(recommendation['evidence'])}</p>" if recommendation.get("evidence") else ""}
        <span class="recommendation-confidence">
            Confidence: {html.escape(recommendation["confidence"])}
        </span>
    </article>
    """
    st.markdown(
        recommendation_html,
        unsafe_allow_html=True,
    )

st.markdown(
    "</div>",
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
        "Ask about key signals, trend shifts, likely drivers, or request a chart change…"
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


st.caption(
    "No-BS rule: charts highlight predictive patterns; validate source records before making decisions."
)
