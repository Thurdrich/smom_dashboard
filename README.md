# SMOM Manpower & Travel Readiness Dashboard

SMOM Dashboard is a Streamlit **Manpower & Travel Readiness Studio** for maritime operations. Upload one or more manpower/travel datasets and the app profiles them, highlights readiness signals, and selects four adaptive charts to reveal trends, concentrations, relationships, and outliers.

## Supported uploads

- CSV (`.csv`)
- Excel (`.xlsx`, `.xls`)
- JSON (`.json`)

Multiple files can be uploaded at once. They are combined by column name, with a `Source file` field added so the result remains traceable. The app only analyzes uploaded data (no demo/preview fallback dataset).

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

The Streamlit app entrypoint is `app.py`. Streamlit Cloud can deploy the `main` branch directly and will refresh after the commit is built.

## How the analysis works

The dashboard detects numeric, categorical, and date-like fields without requiring a particular schema. It then generates four views from the available signals: a trend or distribution, a grouped comparison or relationship, a correlation heatmap or composition view, and a time/category mix or outlier view. The strategic note is exploratory guidance—not a substitute for validating the source data or operational context.
