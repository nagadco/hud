from train_model import train_and_predict
from predict import predict_new_data


def main():
    model = train_and_predict("data/TriningData.csv")
    predictions = predict_new_data(model, "data/mapp-Al-rawabi_test.csv")
    predictions.to_csv("your_predictions.csv", index=False, encoding="utf-8")


if __name__ == "__main__":
    main()
