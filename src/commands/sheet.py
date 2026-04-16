from __future__ import annotations

import os


def sheet_url() -> str:
    sid = os.environ.get("GOOGLE_SHEETS_SPREADSHEET_ID", "")
    return f"https://docs.google.com/spreadsheets/d/{sid}/edit"
