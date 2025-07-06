import argparse
import json
import os
import random
from datetime import datetime
from typing import List, Dict, Any, Optional

import pandas as pd
import requests


STATUS_KEYS = {
    "closed": "closed",
    "off plan": "off_plan",
    "off_plan": "off_plan",
    "in progress": "in_progress",
    "in_progress": "in_progress",
    "open": "open",
    "planned": "planned",
}

# A small pool of user agent strings to randomize requests
USER_AGENTS: List[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0 Safari/537.36",
]


def fetch_from_url(url: str, user_agents: Optional[List[str]] = None) -> str:
    """Fetch data from a URL, raising an error if the request fails."""
    headers = {"User-Agent": random.choice(user_agents or USER_AGENTS)}
    response = requests.get(url, timeout=30, headers=headers)
    response.raise_for_status()
    return response.text


def read_from_file(path: str) -> str:
    """Read data from a local file."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def parse_raw_text(text: str) -> Dict[str, Any]:
    """Parse a simple raw text format into a structured dict."""
    districts = []
    blocks = text.strip().split("\n\n")
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        name = lines[0]
        info = {k: 0 for k in STATUS_KEYS.values()}
        for line in lines[1:]:
            if ":" in line:
                key, value = map(str.strip, line.split(":", 1))
                key = STATUS_KEYS.get(key.lower())
                if key:
                    try:
                        info[key] = int(value)
                    except ValueError:
                        info[key] = 0
        districts.append({"name": name, **info})
    return {"districts": districts}


def load_data(source: str, from_url: bool, user_agents: Optional[List[str]] = None) -> Dict[str, Any]:
    """Load data from a URL or file and parse JSON or raw text."""
    raw = fetch_from_url(source, user_agents) if from_url else read_from_file(source)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return parse_raw_text(raw)


def normalize_district(d: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure all expected keys exist and normalize names."""
    result = {"name": d.get("name", "")}
    for key in STATUS_KEYS.values():
        result[key] = int(d.get(key, 0) or 0)
    return result


def process_districts(data: Dict[str, Any]) -> pd.DataFrame:
    districts = [normalize_district(d) for d in data.get("districts", [])]
    rows = []
    for d in districts:
        total = sum(
            d[k]
            for k in ["closed", "off_plan", "in_progress", "open", "planned"]
        )
        completed = d["closed"] + d["off_plan"]
        remaining = d["open"] + d["in_progress"] + d["planned"]
        completion_pct = (completed / total * 100) if total else 0
        if completed == total and total > 0:
            status = "Closed"
        elif completed == 0:
            status = "Open"
        else:
            status = "In Progress"
        rows.append(
            {
                "District Name": d["name"],
                "Total Territories": total,
                "Closed": d["closed"],
                "Off Plan": d["off_plan"],
                "In Progress": d["in_progress"],
                "Open": d["open"],
                "Planned": d["planned"],
                "Completed Total": completed,
                "Remaining Total": remaining,
                "Completion %": round(completion_pct, 2),
                "Overall District Status": status,
            }
        )
    return pd.DataFrame(rows)


def save_to_excel(df: pd.DataFrame, output_dir: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"territory_status_summary_{timestamp}.xlsx"
    path = os.path.join(output_dir, filename)
    df.to_excel(path, index=False, engine="openpyxl")
    return path


def main():
    parser = argparse.ArgumentParser(description="Generate territory status summary")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="URL to fetch territory data from")
    group.add_argument("--file", help="Path to local data file")
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory to write the Excel summary to",
    )
    args = parser.parse_args()

    try:
        data = load_data(args.url or args.file, from_url=bool(args.url), user_agents=USER_AGENTS)
    except Exception as exc:
        raise SystemExit(f"Failed to load data: {exc}")

    df = process_districts(data)
    if df.empty:
        raise SystemExit("No district data found")

    try:
        excel_path = save_to_excel(df, args.output_dir)
        print(f"Summary written to {excel_path}")
    except Exception as exc:
        raise SystemExit(f"Failed to save Excel file: {exc}")


if __name__ == "__main__":
    main()

