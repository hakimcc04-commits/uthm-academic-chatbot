import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "academic_chatbot_dataset.csv"

class SemanticSearchEngine:
    def __init__(self, dataset_path=DATASET_PATH):
        self.dataset_path = dataset_path
        self.df = None
        self.vectorizer = None
        self.tfidf_matrix = None
        self.load_and_index()

    def load_and_index(self):
        if not self.dataset_path.exists():
            return
        self.df = pd.read_csv(self.dataset_path)
        # Combine question, intent, and Malay/English responses into search corpus
        corpus = (
            self.df["question"].fillna("") + " " +
            self.df["intent"].fillna("") + " " +
            self.df["response_bm"].fillna("")
        )
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=3000)
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)

    def search(self, query, top_k=3, min_similarity=0.25):
        if self.vectorizer is None or self.tfidf_matrix is None:
            return []
        query_vec = self.vectorizer.transform([query])
        similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in top_indices:
            score = float(similarities[idx])
            if score >= min_similarity:
                row = self.df.iloc[idx].to_dict()
                row["similarity_score"] = round(score, 4)
                results.append(row)
        return results

semantic_engine = SemanticSearchEngine()
