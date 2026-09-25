# SMOM Dashboard

SMOM Dashboard is a domain-neutral Streamlit **Strategic Insight Studio**. Upload one or more tabular datasets and the app profiles approved fields, selects four useful views, and produces descriptive observations, data-quality gaps, and potential-risk signals.

## Privacy-first workflow

- Supported uploads: CSV, XLSX/XLS, JSON, Parquet, and XML.
- Direct identifiers such as addresses, phone numbers, emails, and employee/personnel IDs are detected and omitted before profiling by default.
- Name-like fields are owner-controlled and can be omitted or allowed for the current session.
- The visible **Privacy report** shows what was omitted, why it was detected, and what remains available to analysis.
- Only the approved/sanitized frame is used for filters, charts, findings, previews, and downloads.
- Uploaded files are processed in-session and are not written to the repository.

This application privacy boundary does not replace deployment authentication, HTTPS, authorization, storage controls, or a managed secret store.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Analysis behavior

The app detects numeric, date-like, categorical, and text fields without assuming a business domain. It generates adaptive composition, timeline or relationship, segment-comparison, and missingness views. Findings identify patterns and gaps for validation; they do not invent business meaning or replace source-data review.
