# SMOM Dashboard

SMOM Dashboard is a domain-neutral Streamlit **Strategic Insight Studio**. Upload one or more tabular datasets and the app profiles the approved fields, selects four useful views, and produces direct observations, data-quality gaps, and potential-risk signals.

## Privacy-first workflow

- Supported uploads: CSV, XLSX/XLS, JSON, Parquet, and XML.
- Direct identifiers such as addresses, phone numbers, emails, employee/personnel IDs, and similar fields are detected and omitted before profiling by default.
- Name-like fields are owner-controlled. The data owner can permit names for the current session or omit them.
- The visible **Privacy report** shows what was omitted, why it was detected, and what remains available to analysis.
- Only the approved/sanitized frame is used for charts, findings, the data preview, and downloads.
- Uploaded files are processed in-session and are not written to the repository.

This application privacy boundary does not replace deployment authentication, HTTPS, authorization, storage controls, or a managed secret store. For a public deployment, put authentication in front of Streamlit using the hosting provider or an identity-aware proxy (for example OAuth/OIDC, Microsoft Entra ID, Cloudflare Access, or an equivalent service).

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Analysis behavior

The app detects numeric, date-like, categorical, and text fields without assuming a business domain. It generates four adaptive views: composition/distribution, timeline or relationship, segment comparison, and missingness/data quality. It also surfaces exception-like text, duplicate-style gaps, malformed values, concentration, and missingness where the data supports those findings. The output is deliberately descriptive and flags findings for validation rather than inventing business meaning.
