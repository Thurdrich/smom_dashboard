# SMOM Dashboard

This repository contains a Streamlit dashboard for the Strategic Manpower Optimization Model.

## Deployment

The app entrypoint is `app.py`. Streamlit Cloud can deploy this repository directly.

### Streamlit Cloud setup

1. Connect your GitHub repository `Thurdrich/smom_dashboard` to Streamlit Cloud.
2. Choose the `main` branch.
3. Set the app file path to `app.py`.
4. Optionally add Streamlit secrets in the app settings:
   - `admin_password`
   - `latiimer_password`

### Local launch

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Notes

- The app now searches for the dataset file automatically using one of these names:
  - `clean_mcs.csv`
  - `CLEANED_JOINED_MODEL CRIT SCORE_DATA.csv`
  - `CLEANED_JOINED_MODEL CRIT SCORE_DATA.csv.csv`
- If you already have `smomdashboard.streamlit.app`, the app should update automatically when you push to `main`.

## GitHub CI

A GitHub Actions workflow is included at `.github/workflows/streamlit-ci.yml`.
It installs dependencies and validates `app.py` on each push or pull request to `main`.
