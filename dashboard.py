"""Travel dashboard aggregation and local question answering."""

from io import BytesIO
from pathlib import Path
import re
from zipfile import BadZipFile

import pandas as pd


SUPPORTED_TYPES = ["csv", "xlsx", "xls", "json", "parquet", "xml"]


def read_upload(name, content):
    suffix = Path(name).suffix.lower()
    stream = BytesIO(content)
    if suffix == ".csv":
        for encoding in ("utf-8-sig", "cp1252", "latin1"):
            try:
                stream.seek(0)
                return pd.read_csv(stream, encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError("Could not decode CSV file")
    if suffix in (".xlsx", ".xls"):
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
    for uploaded in files:
        try:
            frame = read_upload(uploaded.name, uploaded.getvalue()).copy()
            frame.columns = [str(column).strip() for column in frame.columns]
            if not all(frame.columns) or not frame.columns.is_unique:
                raise ValueError("Column names must be nonempty and unique")
            if "Source file" in frame.columns:
                raise ValueError("The reserved column name 'Source file' is already in the file")
            frame = frame.dropna(how="all")
            frame["Source file"] = uploaded.name
            frames.append(frame)
        except (ValueError, TypeError, ImportError, OSError, UnicodeError, SyntaxError, EOFError, BadZipFile) as exc:
            errors.append(f"{uploaded.name}: {exc}")
    return (pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()), errors


def default_field(columns, candidates):
    normalized = {re.sub(r"\s+", " ", str(c).strip().lower()): c for c in columns}
    return next((normalized[candidate] for candidate in candidates if candidate in normalized), None)


def parse_movement_dates(series):
    def parse(value):
        if pd.isna(value) or str(value).strip() == "":
            return pd.NaT
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return pd.to_datetime(value, unit="D", origin="1899-12-30", errors="coerce")
        return pd.to_datetime(value, errors="coerce")

    return pd.to_datetime(series.map(parse), errors="coerce").dt.normalize()


def grouped_counts(data, group, traveler=None):
    if not group:
        return None
    labels = data[group].fillna("").astype(str).str.strip().replace("", "Missing")
    if traveler:
        names = data[traveler].fillna("").astype(str).str.strip().str.replace(r"\s+", " ", regex=True).str.casefold()
        frame = pd.DataFrame({"Group": labels, "Traveler": names})
        frame = frame[frame["Traveler"] != ""]
        counts = frame.groupby("Group", sort=False)["Traveler"].nunique()
    else:
        counts = labels.value_counts()
    return counts.sort_values(ascending=False).rename_axis("Group").reset_index(name="Count")


def movement_counts(data, date_column):
    if not date_column:
        return None
    parsed = parse_movement_dates(data[date_column])
    return parsed.dropna().value_counts().sort_index().rename_axis("Date").reset_index(name="Count")


def chart_tables(data, fields):
    return {
        "status": grouped_counts(data, fields["status"]),
        "vessel": grouped_counts(data, fields["vessel"], fields["traveler"]) if fields["traveler"] else None,
        "date": movement_counts(data, fields["date"]),
        "location": grouped_counts(data, fields["location"], fields["traveler"]) if fields["traveler"] else None,
    }


def local_answer(question, data, fields, tables):
    q = question.casefold().strip()
    if data.empty:
        return "The current filters contain no rows."
    keys = {
        "status": ("status", "statuses"),
        "vessel": ("vessel", "ship", "ships"),
        "date": ("date", "timeline", "trend", "movement", "movements"),
        "location": ("location", "port", "destination"),
    }
    matches = [key for key, words in keys.items() if any(re.search(r"\b" + word + r"\b", q) for word in words)]
    if len(matches) > 1:
        return "Please ask about one chart at a time: status, vessel, movement dates, or location."
    if matches:
        key = matches[0]
        table = tables[key]
        if table is None:
            return f"The {key} chart is unavailable. Select the required fields in the sidebar."
        if table.empty:
            return f"The {key} chart has no usable values in the current data."
        if key == "date":
            peak = table.loc[table["Count"].idxmax()]
            return (f"The timeline uses {fields['date']} and counts movement rows. "
                    f"It shows {table['Count'].sum():,} dated rows from "
                    f"{table['Date'].min():%Y-%m-%d} to {table['Date'].max():%Y-%m-%d}; "
                    f"the first peak is {peak['Date']:%Y-%m-%d} with {peak['Count']:,} movements.")
        unit = "movement rows" if key == "status" else "distinct named travelers"
        if any(word in q for word in ("least", "lowest", "smallest", "fewest")):
            row = table.iloc[-1]
            return f"The smallest {key} group is {row['Group']}: {row['Count']:,} {unit}."
        if any(word in q for word in ("most", "highest", "largest", "top", "maximum")):
            row = table.iloc[0]
            return f"The largest {key} group is {row['Group']}: {row['Count']:,} {unit}."
        # Match a complete category rather than guessing from partial names.
        for _, row in table.iterrows():
            label = str(row["Group"])
            if label.casefold() not in keys[key] and re.search(r"(?<!\w)" + re.escape(label.casefold()) + r"(?!\w)", q):
                return f"{label}: {row['Count']:,} {unit} in the {key} chart."
        values = "; ".join(f"{row['Group']}: {row['Count']:,}" for _, row in table.head(10).iterrows())
        suffix = f" Showing 10 of {len(table)} groups." if len(table) > 10 else ""
        return f"{key.title()} chart ({unit}): {values}.{suffix}"
    if any(word in q for word in ("rows", "records", "total", "how many")):
        text = f"The current filtered data contains {len(data):,} movement rows."
        if fields["traveler"]:
            names = data[fields["traveler"]].fillna("").astype(str).str.strip().str.replace(r"\s+", " ", regex=True).str.casefold()
            text += f" It contains {names[names != ''].nunique():,} distinct named travelers."
        return text
    return ("I can summarize movement row counts, status, vessel, location, and the date timeline. "
            "Try “Which vessel has the most travelers?” or “Summarize the movement dates.” "
            "I cannot answer arbitrary questions or infer causes.")
