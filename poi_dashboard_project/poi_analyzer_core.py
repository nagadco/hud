"""Core analysis logic for POI performance."""

from __future__ import annotations

import pandas as pd
from pandas import DataFrame


class POIManagementAnalyzer:
    """Analyze POI logs and compute surveyor performance metrics."""

    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.df: DataFrame | None = None

    def load_data(self) -> DataFrame:
        """Load and clean the CSV data."""
        if self.df is not None:
            return self.df

        try:
            df = pd.read_csv(self.csv_path, encoding="utf-8", on_bad_lines="skip")
        except UnicodeDecodeError:
            df = pd.read_csv(self.csv_path, encoding="latin1", on_bad_lines="skip")

        # Basic cleaning and validation
        df = df.dropna(subset=["id", "created_by"])
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        df = df.dropna(subset=["created_at"])
        df["quality_score"] = pd.to_numeric(df.get("quality_score"), errors="coerce")
        df = df.dropna(subset=["quality_score"])
        self.df = df
        return df

    def analyze(self) -> DataFrame:
        """Compute performance metrics per surveyor."""
        df = self.load_data().copy()

        counts = df.groupby("created_by").size().rename("submissions")
        time_spans = (
            df.groupby("created_by")["created_at"].agg(["min", "max"])
            .assign(hours=lambda x: (x["max"] - x["min"]).dt.total_seconds() / 3600)
        )
        submissions_per_hour = counts / time_spans["hours"].replace(0, pd.NA)

        mean_quality = df.groupby("created_by")["quality_score"].mean()
        std_quality = df.groupby("created_by")["quality_score"].std().fillna(0)

        summary = pd.DataFrame(
            {
                "submissions_per_hour": submissions_per_hour,
                "avg_quality_score": mean_quality,
                "quality_std_dev": std_quality,
            }
        )

        summary["tier"] = pd.cut(
            summary["avg_quality_score"],
            bins=[0, 0.7, 0.85, 1.0],
            labels=["Bronze", "Silver", "Gold"],
            include_lowest=True,
        )

        return summary.reset_index()

    def get_summary(self) -> DataFrame:
        """Public method returning the computed summary."""
        return self.analyze()

