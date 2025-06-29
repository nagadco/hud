import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)
from imblearn.over_sampling import RandomOverSampler

from preprocess import preprocess_data


def train_and_predict(filepath: str):
    """Train a RandomForest model and print evaluation metrics."""
    df = preprocess_data(filepath)

    X = df.drop(columns=["Name", "Category", "Label"], errors="ignore")
    y = df["Label"]

    ros = RandomOverSampler(random_state=42)
    X_res, y_res = ros.fit_resample(X, y)

    X_train, X_test, y_train, y_test = train_test_split(
        X_res, y_res, test_size=0.3, random_state=42, stratify=y_res
    )

    model = RandomForestClassifier(n_estimators=40, random_state=42)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)

    acc = accuracy_score(y_test, y_pred)
    print(f"Accuracy: {acc:.4f}")
    print("Classification Report:")
    print(classification_report(y_test, y_pred, zero_division=0))

    cm = confusion_matrix(y_test, y_pred)
    print("Confusion Matrix:")
    print(cm)

    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues")
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.show()

    tn, fp, fn, tp = cm.ravel()
    print(f"TP: {tp}, TN: {tn}, FP: {fp}, FN: {fn}")

    return model
