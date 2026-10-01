import os
import sys
import joblib
from pathlib import Path
import pandas as pd
import numpy as np

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent
dataset_path = BASE_DIR / "academic_chatbot_dataset.csv"
model_output_dir = BASE_DIR / "models"
model_output_dir.mkdir(exist_ok=True)
model_file = model_output_dir / "local_neural_model.pkl"

def train_local_neural_model():
    print("🚀 Training Local Neural Network Model (Fine-Tuned Classifier)...")
    if not dataset_path.exists():
        print(f"Error: {dataset_path} not found.")
        return

    df = pd.read_csv(dataset_path)
    X = df["question"].fillna("").astype(str)
    y = df["intent"].fillna("").astype(str)

    # Train / Test split without stratify constraint for single-member classes
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.15, random_state=42)

    # Build Pipeline: Word + Char N-gram TF-IDF + Multi-Layer Perceptron Neural Net
    pipeline = make_pipeline(
        TfidfVectorizer(ngram_range=(1, 3), analyzer="word", min_df=1, max_features=10000),
        MLPClassifier(hidden_layer_sizes=(128, 64), max_iter=300, random_state=42, early_stopping=True)
    )

    pipeline.fit(X_train, y_train)

    # Evaluation on test set
    y_pred = pipeline.predict(X_test)
    acc = accuracy_score(y_test, y_pred)

    print(f"✅ Training Complete! Test Accuracy: {acc * 100:.2f}%")
    
    # Save trained model
    joblib.dump(pipeline, model_file)
    print(f"💾 Saved Local Neural Model to: {model_file}")

if __name__ == "__main__":
    train_local_neural_model()
