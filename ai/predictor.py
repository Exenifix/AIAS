from pickle import load

from numpy import array
from sklearn.ensemble import RandomForestClassifier

from ai.analyser import analyse_sample

model: RandomForestClassifier


def load_model():
    global model
    with open("ai/models/model.ai", "rb") as f:
        model = load(f)


def is_spam(sample: str) -> bool:
    return bool(model.predict(array(analyse_sample(sample)[:4], ndmin=2))[0])
