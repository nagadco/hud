import pandas as pd
import re


def contains_arabic_or_english_or_digits(text: str) -> bool:
    """Return True if text contains Arabic, English letters or digits."""
    if not isinstance(text, str):
        text = str(text)
    pattern = re.compile(r"[A-Za-z0-9\u0600-\u06FF]")
    return bool(pattern.search(text))


def preprocess_data(filepath: str) -> pd.DataFrame:
    """Load and preprocess data from a CSV file.

    Parameters
    ----------
    filepath : str
        Path to the CSV file.

    Returns
    -------
    pandas.DataFrame
        Preprocessed DataFrame with binary features and encoded labels.
    """
    df = pd.read_csv(filepath, encoding="utf-8")

    # Standardize column names
    df.columns = df.columns.str.strip()

    # Encode label
    if "Label" in df.columns:
        df["Label"] = df["Label"].map({"Good": 1, "Bad": 0})

    # Convert rating to binary >2 -> 1 else 0
    if "Rating" in df.columns:
        df["Rating"] = df["Rating"].apply(
            lambda x: 1 if pd.to_numeric(x, errors="coerce") > 2 else 0
        )

    # Binary presence for other columns
    feature_cols = [c for c in df.columns if c not in ["Name", "Category", "Label"]]
    for col in feature_cols:
        if col == "Rating":
            continue
        df[col] = df[col].apply(
            lambda x: 0
            if pd.isna(x) or str(x).strip() == "" or str(x).strip().lower() == "missing"
            else 1
        )

    # Rows with names not containing Arabic, English, or digits -> set features to 0
    if "Name" in df.columns:
        mask = ~df["Name"].apply(contains_arabic_or_english_or_digits)
        df.loc[mask, feature_cols] = 0

    return df
