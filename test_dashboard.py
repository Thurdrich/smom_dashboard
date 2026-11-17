import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from dashboard import chart_tables, default_field, load_uploads, local_answer, parse_movement_dates


class Upload:
    def __init__(self, path):
        self.path = Path(path)
        self.name = self.path.name

    def getvalue(self):
        return self.path.read_bytes()


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.data = pd.DataFrame({
            "STATUS": ["PENDING", "PENDING", "DONE", None],
            "CIVMAR/PER": ["Smith", " smith ", "Jones", None],
            "VESSEL": ["A", "A", "A", "B"],
            "DATE 1": ["9/11/2026", "9/11/2026", "invalid", "9/12/2026"],
            "LOCATION": ["Port", "Port", "Other", "Port"],
        })
        self.fields = {"status": "STATUS", "traveler": "CIVMAR/PER", "vessel": "VESSEL",
                       "date": "DATE 1", "location": "LOCATION"}

    def test_chart_counts_and_missing_data(self):
        tables = chart_tables(self.data, self.fields)
        self.assertEqual(dict(tables["status"].values), {"PENDING": 2, "DONE": 1, "Missing": 1})
        self.assertEqual(dict(tables["vessel"].values), {"A": 2})
        self.assertEqual(dict(tables["location"].values), {"Port": 1, "Other": 1})
        self.assertEqual(tables["date"]["Count"].tolist(), [2, 1])
        self.assertEqual(str(tables["date"]["Date"].iloc[0].date()), "2026-09-11")

    def test_empty_or_unselected_fields_do_not_invent_counts(self):
        fields = {**self.fields, "traveler": None, "date": None}
        tables = chart_tables(self.data, fields)
        self.assertIsNone(tables["vessel"])
        self.assertIsNone(tables["location"])
        self.assertIsNone(tables["date"])
        self.assertIn("unavailable", local_answer("Which vessel has the most?", self.data, fields, tables))

    def test_dates_support_excel_serials(self):
        dates = parse_movement_dates(pd.Series([46276, "9/11/2026", None, "invalid"]))
        self.assertEqual(str(dates.iloc[0].date()), "2026-09-11")
        self.assertEqual(dates.notna().sum(), 2)

    def test_chat_uses_same_filtered_chart_aggregates(self):
        filtered = self.data.loc[self.data["STATUS"] == "PENDING"]
        tables = chart_tables(filtered, self.fields)
        self.assertIn("A: 1", local_answer("Which vessel has the most travelers?", filtered, self.fields, tables))
        self.assertIn("2 dated rows", local_answer("Summarize movement dates", filtered, self.fields, tables))
        self.assertIn("2 movement rows", local_answer("How many records?", filtered, self.fields, tables))
        self.assertIn("one chart at a time", local_answer("Compare vessel and location", filtered, self.fields, tables))

    def test_bundled_travel_file(self):
        for path in ("clean_mcs.csv", "CURRENT MOVEMENT DATA.xlsx"):
            with self.subTest(path=path):
                data, errors = load_uploads([Upload(path)])
                self.assertFalse(errors)
                fields = {
                    "status": default_field(data.columns, ("status",)),
                    "traveler": default_field(data.columns, ("civmar/per",)),
                    "vessel": default_field(data.columns, ("vessel",)),
                    "date": default_field(data.columns, ("date 1",)),
                    "location": default_field(data.columns, ("location",)),
                }
                tables = chart_tables(data, fields)
                self.assertEqual(fields["date"], "DATE 1")
                self.assertTrue(all(table is not None and not table.empty for table in tables.values()))
                self.assertEqual(tables["status"]["Count"].sum(), len(data))

    def test_streamlit_charts_chat_and_filter_change(self):
        data, errors = load_uploads([Upload("clean_mcs.csv")])
        with patch("dashboard.load_uploads", return_value=(data, errors)):
            app = AppTest.from_file("app.py").run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.get("plotly_chart")), 4)
            app.chat_input[0].set_value("Which vessel has the most travelers?").run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.chat_message), 2)
            self.assertIn("largest vessel", app.chat_message[1].markdown[0].value)
            app.multiselect[0].select("PENDING").run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.chat_message), 0)


if __name__ == "__main__":
    unittest.main()
