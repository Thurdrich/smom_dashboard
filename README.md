# SMOM Travel Analysis Dashboard

Upload travel data to view the CIVMAR overview: total travelers and status/lodging metrics, travelers by vessel and direction, travelers by status, and the top ten ratings by travel volume. The charts link to detail pages for Traveler Ratings, Traveler Flight Dates, and the CIVMAR tracker by status. A local, rule-based chat below the overview summarizes the same filtered data; it is not a general-purpose AI assistant.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Upload CSV, Excel, JSON, Parquet, or XML files in the sidebar. Multiple files are combined by column name. Excel uploads use the first sheet. No sample data is loaded automatically and no data is sent to an external AI service.

Check or change the detected field selections in the sidebar. `DATE 1` is the preferred default expected-movement date; if it is absent, a recognized expected, planned, or travel date is selected. Otherwise choose a date explicitly. Missing or invalid dates are excluded from the flight-date chart and table. Traveler totals, status metrics, rating, vessel, and direction counts deduplicate traveler names or IDs within each group, ignoring case and extra whitespace; rows without a traveler name are excluded when a traveler field is selected. The flight-date chart hover details list the travelers counted in each date/direction bar. Cancellation percentage counts travelers with a cancelled status over total travelers. Requires Lodging counts travelers with a nonempty lodging field. Missing group values appear as `Missing`.

Filters affect all charts and chat. Chat history is cleared when the data, filters, or field selections change. Example questions: “Which vessel has the most travelers?”, “Summarize the status chart”, “How many records are there?”, and “Summarize the movement dates”. The assistant cannot answer arbitrary questions or determine causes.
