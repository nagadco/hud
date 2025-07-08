"""Run the analysis and export results to Google Sheets."""

from __future__ import annotations

import argparse

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from poi_analyzer_core import POIManagementAnalyzer


def export_to_sheets(csv_path: str, credentials_path: str, sheet_name: str) -> None:
    analyzer = POIManagementAnalyzer(csv_path)
    summary = analyzer.get_summary()

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_path, scope)
    client = gspread.authorize(creds)

    try:
        sh = client.open(sheet_name)
    except gspread.SpreadsheetNotFound:
        sh = client.create(sheet_name)

    try:
        worksheet = sh.worksheet("Summary")
        worksheet.clear()
    except gspread.WorksheetNotFound:
        worksheet = sh.add_worksheet(title="Summary", rows="100", cols="20")

    worksheet.update([summary.columns.tolist()] + summary.values.tolist())


def main() -> None:
    parser = argparse.ArgumentParser(description="Export POI analysis to Google Sheets")
    parser.add_argument("--csv", default="poi_logs_all_872025.csv", help="Path to CSV log file")
    parser.add_argument(
        "--credentials",
        default="credentials.json",
        help="Path to Google service account credentials JSON",
    )
    parser.add_argument("--sheet", required=True, help="Name of the Google Sheet to use")
    args = parser.parse_args()

    export_to_sheets(args.csv, args.credentials, args.sheet)


if __name__ == "__main__":
    main()

