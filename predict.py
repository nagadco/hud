import pandas as pd

from preprocess import preprocess_data


def predict_new_data(model, new_data_filepath: str) -> pd.DataFrame:
    """Predict labels for new data using a trained model."""
    df = preprocess_data(new_data_filepath)
    names = df.get("Name")
    X_new = df.drop(columns=["Name", "Category", "Label"], errors="ignore")

    preds = model.predict(X_new)
    label_map = {1: "Good", 0: "Bad"}
    results = pd.DataFrame({
        "Name": names,
        "Predicted Label": [label_map.get(int(p), p) for p in preds],
    })
    return results
