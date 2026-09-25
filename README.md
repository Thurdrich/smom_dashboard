# SMOM Dashboard

SMOM Dashboard is a general-purpose Streamlit **Strategic Insight Studio**. Upload one or more tabular datasets and the app automatically profiles them, highlights data quality risks, and selects adaptive charts to reveal trends, concentrations, relationships, and operational exceptions.

## Supported uploads

- CSV (`.csv`)
- Excel (`.xlsx`, `.xls`)
- JSON (`.json`)
- Parquet (`.parquet`)
- XML (`.xml`)

Multiple files can be uploaded at once. They are combined by column name, with a `Source file` field added so the result remains traceable. Before an upload, the app displays an illustrative preview dataset.

## Privacy review

The dashboard includes an owner-controlled privacy review. Sensitive fields can be detected from column names and value patterns, then omitted from analysis and exports. Name-like fields can be masked in previews. Uploaded files are analyzed in-session and are not written back to the repository.

This review is an application-level safeguard; it is not a replacement for authentication, authorization, HTTPS, or managed secrets.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

The Streamlit app entrypoint is `app.py`. Streamlit Cloud can deploy the `main` branch directly and will refresh after the commit is built.

## How the analysis works

The dashboard detects numeric, categorical, date-like, and free-text fields without requiring a fixed schema. It generates four views from the available signals: a composition or distribution view, a timeline or relationship view, a grouped comparison or correlation view, and a data-quality view.

The attention queue identifies exception-like text and formula errors for review. Findings are exploratory guidance only; validate the underlying records and operational context before making decisions.
