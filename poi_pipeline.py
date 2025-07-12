"""Minimal POI Field Operations Management pipeline.

This script demonstrates a simplified data ingestion and processing workflow
based on the system specification. It fetches POI data from the Hudhud API,
performs basic validation and quality scoring, matches POIs to territories,
and uploads results to a Google Sheet.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import List, Dict, Tuple

import pandas as pd
import requests
from shapely.geometry import Point
import geopandas as gpd
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


@dataclass
class POI:
    latitude: float
    longitude: float
    name: str
    category: str
    business_hours: str
    phone: str
    address: str
    photos: List[str]
    status: str
    surveyor_id: str
    timestamp: str
    accuracy_notes: str

    @classmethod
    def from_api(cls, data: Dict) -> "POI":
        return cls(
            latitude=float(data.get("lat") or data.get("latitude")),
            longitude=float(data.get("lng") or data.get("longitude")),
            name=data.get("poi_name") or data.get("name"),
            category=data.get("category") or data.get("poi_category"),
            business_hours=data.get("business_hours", ""),
            phone=data.get("phone", ""),
            address=data.get("address", ""),
            photos=data.get("photos") or data.get("images", []),
            status=data.get("status", ""),
            surveyor_id=data.get("created_by") or data.get("user_id"),
            timestamp=data.get("created_at") or data.get("timestamp"),
            accuracy_notes=data.get("notes", ""),
        )


def fetch_pois(endpoint: str, token: str, page_size: int = 1000) -> List[POI]:
    """Fetch POIs from the Hudhud API using simple pagination."""
    pois: List[POI] = []
    page = 1
    headers = {"Authorization": f"Bearer {token}"}
    while True:
        params = {"page": page, "limit": page_size}
        response = requests.get(endpoint, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        records = data.get("records") or data
        if not records:
            break
        pois.extend(POI.from_api(item) for item in records)
        if len(records) < page_size:
            break
        page += 1
    return pois


def validate_poi(poi: POI) -> Tuple[int, List[str]]:
    """Return a quality score (0-100) and a list of validation errors."""
    required_fields = [
        poi.latitude,
        poi.longitude,
        poi.name,
        poi.category,
        poi.business_hours,
        poi.address,
        poi.photos,
        poi.status,
        poi.surveyor_id,
        poi.timestamp,
    ]
    completeness = sum(bool(f) for f in required_fields) / len(required_fields)

    errors = []
    if not (-90 <= poi.latitude <= 90 and -180 <= poi.longitude <= 180):
        errors.append("invalid_coordinates")
    if len(poi.photos) < 2:
        errors.append("insufficient_photos")

    accuracy = 1.0 if not errors else 0.5
    score = int(completeness * 0.4 * 100 + accuracy * 0.3 * 100 + 20)
    return score, errors


def load_territories(path: str) -> gpd.GeoDataFrame:
    """Load territory polygons from a GeoJSON file."""
    gdf = gpd.read_file(path)
    if not gdf.crs:
        gdf.set_crs(epsg=4326, inplace=True)
    return gdf


def match_territory(poi: POI, territories: gpd.GeoDataFrame) -> str:
    """Return the territory ID containing the POI, or an empty string."""
    point = Point(poi.longitude, poi.latitude)
    matches = territories[territories.contains(point)]
    if not matches.empty:
        return str(matches.iloc[0].get("territory_id", ""))
    return ""


def upload_to_sheet(creds_json: str, sheet_id: str, dataframe: pd.DataFrame, range_name: str = "Sheet1!A1") -> None:
    """Append data to a Google Sheet using a service account."""
    creds = Credentials.from_service_account_file(creds_json, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    service = build("sheets", "v4", credentials=creds)
    body = {"values": [dataframe.columns.tolist()] + dataframe.values.tolist()}
    service.spreadsheets().values().update(spreadsheetId=sheet_id, range=range_name, valueInputOption="RAW", body=body).execute()


def main():
    endpoint = os.getenv("HUDHUD_ENDPOINT")
    token = os.getenv("HUDHUD_TOKEN")
    territories_path = os.getenv("TERRITORIES_GEOJSON")
    creds_path = os.getenv("GOOGLE_CREDS")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")

    if not all([endpoint, token, territories_path, creds_path, sheet_id]):
        raise SystemExit("Missing required environment variables")

    pois = fetch_pois(endpoint, token)
    territories = load_territories(territories_path)

    rows = []
    for poi in pois:
        score, errors = validate_poi(poi)
        territory = match_territory(poi, territories)
        rows.append({
            "name": poi.name,
            "lat": poi.latitude,
            "lon": poi.longitude,
            "category": poi.category,
            "score": score,
            "territory": territory,
            "errors": ",".join(errors),
        })

    df = pd.DataFrame(rows)
    upload_to_sheet(creds_path, sheet_id, df)
    print(f"Uploaded {len(df)} records")


if __name__ == "__main__":
    main()
