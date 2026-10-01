import pandas as pd
import re
import joblib

from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report

SHORT_FORM_MAP = {
    "mcm": "macam",
    "cm": "macam",
    "mna": "mana",
    "mnn": "mana",
    "mn": "mana",
    "nk": "nak",
    "dftar": "daftar",
    "dftr": "daftar",
    "daft": "daftar",
    "rgister": "register",
    "regster": "register",
    "reg": "register",
    "subj": "subjek",
    "sbj": "subjek",
    "sbjct": "subject",
    "subjct": "subject",
    "subjectt": "subject",
    "sbjek": "subjek",
    "sjk": "subjek",
    "sem": "semester",
    "semster": "semester",
    "jdual": "jadual",
    "exm": "exam",
    "xam": "exam",
    "finals": "final",
    "konvo": "konvokesyen",
    "grad": "graduation",
    "yrn": "yuran",
    "fees": "fee",
    "bayr": "bayar",
    "byr": "bayar",
    "tgguh": "tangguh",
    "tanggoh": "tangguh",
}

def clean_text(text):
    text = str(text).lower()
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    words = [SHORT_FORM_MAP.get(word, word) for word in text.strip().split()]
    return " ".join(words)


df = pd.read_csv("academic_chatbot_dataset.csv")

df["clean_question"] = df["question"].apply(clean_text)

X = df["clean_question"]
y = df["intent"]

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=None
)

model = Pipeline([
    ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
    ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced"))
])

model.fit(X_train, y_train)

y_pred = model.predict(X_test)

print("Accuracy:", accuracy_score(y_test, y_pred))
print(classification_report(y_test, y_pred))

joblib.dump(model, "academic_chatbot_model.pkl")

print("Model trained and saved successfully.")
