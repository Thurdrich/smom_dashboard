# SMOM Adaptive Insight Dashboard

SMOM Dashboard is a Streamlit **Adaptive Insight Dashboard**. Upload one or more datasets and the app profiles them, computes dataset signal/readiness indicators, and renders a polished four-chart overview tuned to the detected schema and filtered data.

## Supported uploads

- CSV (`.csv`)
- Excel (`.xlsx`, `.xls`)
- JSON (`.json`)
- Parquet (`.parquet`)
- XML (`.xml`)

Multiple files can be uploaded at once. They are combined by column name, with a `Source file` field added so the result remains traceable.

The app is local-only for analysis in-session:
- no external AI API calls
- no external data transfer
- no bundled preview/demo fallback dataset

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

The Streamlit app entrypoint is `app.py`. Streamlit Cloud can deploy the `main` branch directly and will refresh after the commit is built.

## How the analysis works

The dashboard detects numeric, categorical, text, and date-like fields without requiring a fixed schema.

- **Core dashboard:** always renders a 4-chart adaptive overview. Each slot uses a prioritized chart-family fallback chain (for example composition-like, trend-like, relationship-like, distribution-like, then summary/count views) based on the detected schema.
- **Focused custom chart (optional):** you can add one extra chart without replacing the core four-chart overview.
- **Assistant recommendations:** after chart rendering, recommendations are generated from findings in the current filtered dataset and presented as follow-up guidance.
- **Local assistant chat:** a rule-based assistant answers questions using only the uploaded/filtered data.
- **Dataset signal summary:** readiness and signal indicators are shown from coverage/schema/trendability/signal density in the current filtered slice.
