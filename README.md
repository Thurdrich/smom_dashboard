# SMOM Predictive Insight Dashboard

SMOM Dashboard is a Streamlit **Predictive Insight Studio**. Upload one or more datasets and the app profiles them, scores prediction readiness, and selects four adaptive charts to reveal trends, concentrations, relationships, and outliers.

## Supported uploads

- CSV (`.csv`)
- Excel (`.xlsx`, `.xls`)
- JSON (`.json`)

Multiple files can be uploaded at once. They are combined by column name, with a `Source file` field added so the result remains traceable. The app only analyzes uploaded data locally (no demo/preview fallback dataset and no external data transfer).

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

The Streamlit app entrypoint is `app.py`. Streamlit Cloud can deploy the `main` branch directly and will refresh after the commit is built.

## How the analysis works

The dashboard detects numeric, categorical, and date-like fields without requiring a particular schema. It then generates four views from available signals and supports an optional focused chart, including a field-level signal-strength view. The app also reports a prediction-readiness score based on data coverage, schema richness, trendability, and signal density. Recommendations and assistant responses are generated from the active filtered dataset only.
