# SMOM Travel Analysis Dashboard

Upload travel data to view four charts in a 2×2 layout: movement rows by status, distinct travelers by vessel, movement rows by expected date, and distinct travelers by location. A local, rule-based chat below the charts summarizes the same filtered data; it is not a general-purpose AI assistant.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Upload CSV, Excel, JSON, Parquet, or XML files in the sidebar. Multiple files are combined by column name. Excel uploads use the first sheet. No sample data is loaded automatically and no data is sent to an external AI service.

Check or change the detected field selections in the sidebar. `DATE 1` is the preferred default expected-movement date; if it is absent, a recognized expected, planned, or travel date is selected. Otherwise choose a date explicitly. Missing or invalid dates are excluded from the timeline. Status and timeline counts are rows, not unique travelers. Vessel and location counts deduplicate traveler names or IDs within each group, ignoring case and extra whitespace; rows with no traveler are excluded. A traveler can appear in more than one group. Missing group values appear as `Missing`.

Filters affect all charts and chat. Chat history is cleared when the data, filters, or field selections change. Example questions: “Which vessel has the most travelers?”, “Summarize the status chart”, “How many records are there?”, and “Summarize the movement dates”. The assistant cannot answer arbitrary questions or determine causes.
