import os
import sys
import time
import re
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import types

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

_client = None
_df_dataset = None
_df_docs = None

def get_client():
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            _client = genai.Client(api_key=api_key)
    return _client

def load_data():
    global _df_dataset, _df_docs
    if _df_dataset is None:
        dataset_path = BASE_DIR / "academic_chatbot_dataset.csv"
        if dataset_path.exists():
            df = pd.read_csv(dataset_path)
            _df_dataset = df.drop_duplicates(subset=["intent", "response_bm"]).copy()
        else:
            _df_dataset = pd.DataFrame()

    if _df_docs is None:
        doc_path = BASE_DIR / "documents.csv"
        if doc_path.exists():
            _df_docs = pd.read_csv(doc_path).copy()
        else:
            _df_docs = pd.DataFrame()

def retrieve_dynamic_context(user_query: str, max_qa: int = 6) -> str:
    load_data()
    
    query_words = set(re.findall(r"\w+", user_query.lower()))
    stop_words = {"yang", "dan", "di", "ke", "ini", "itu", "saya", "nak", "bagaimana", "macam", "mana", "bila", "apa", "berapa", "is", "the", "in", "to", "what", "how"}
    meaningful_words = query_words - stop_words
    if not meaningful_words:
        meaningful_words = query_words

    lines = ["=== UTHM ACADEMIC KNOWLEDGE BASE (RELEVANT FACTS) ==="]

    scored_rows = []
    if _df_dataset is not None and not _df_dataset.empty:
        for idx, row in _df_dataset.iterrows():
            q_text = (str(row.get("question", "")) + " " + str(row.get("intent", ""))).lower()
            q_words = set(re.findall(r"\w+", q_text))
            overlap = len(meaningful_words & q_words)
            scored_rows.append((overlap, row))
        
        scored_rows.sort(key=lambda x: x[0], reverse=True)
        top_qa = scored_rows[:max_qa]
        
        lines.append("\n--- RELEVANT FREQUENTLY ASKED QUESTIONS ---")
        for score, row in top_qa:
            q = str(row.get("question", "")).strip()
            r_bm = str(row.get("response_bm", "")).strip()
            r_en = str(row.get("response_en", "")).strip()
            url = str(row.get("source_url", "")).strip()
            lines.append(f"Q: {q}")
            lines.append(f"A (BM): {r_bm}")
            lines.append(f"A (EN): {r_en}")
            if url and url != "nan":
                lines.append(f"Source: {url}")
            lines.append("-")

    if _df_docs is not None and not _df_docs.empty:
        lines.append("\n--- OFFICIAL UTHM DOCUMENTS & FORMS ---")
        for idx, row in _df_docs.iterrows():
            doc_name = str(row.get("document_name", "")).strip()
            summary = str(row.get("summary", "")).strip()
            url = str(row.get("source_url", "")).strip()
            file_p = str(row.get("file_path", "")).strip()
            lines.append(f"Document: {doc_name}")
            lines.append(f"Summary: {summary}")
            if url and url != "nan":
                lines.append(f"URL: {url}")
            if file_p and file_p != "nan":
                lines.append(f"File Path: {file_p}")
            lines.append("-")

    return "\n".join(lines)

SYSTEM_INSTRUCTIONS = """Anda adalah Pembantu Pintar AI Akademik Rasmi Universiti Tun Hussein Onn Malaysia (UTHM Academic Chatbot).

Tugas utama anda:
1. Menjawab semua soalan akademik pengguna (pelajar, pensyarah, orang awam) secara sangat tepat, teliti, mesra, dan berstruktur.
2. Memahami pelbagai variasi bahasa termasuk Bahasa Melayu pasar / slang / ejaan ringkas (contoh: 'mcm', 'nk', 'dpt', 'utk', '2nd class', 'gugur subjek', 'dekan', 'psm', 'pointer', 'ptptn').
3. Menggunakan UTHM Academic Knowledge Base yang disediakan sebagai rujukan fakta utama. Jangan mereka maklumat yang bertentangan dengan maklumat UTHM.
4. Menjawab mengikut bahasa yang digunakan oleh pengguna (Bahasa Melayu jika soalan BM/slang BM, English jika soalan Inggeris).
5. Sertakan pautan rasmi (Source URL / Document URL) jika relevan untuk memudahkan pengguna.
6. Berikan susunan jawapan yang kemas menggunakan kemudahan bullet points (* atau 1. 2. 3.) serta perenggan yang mudah dibaca.
"""

def query_gemini(user_query: str, context: dict = None) -> str:
    client = get_client()
    if not client:
        return None

    dynamic_kb = retrieve_dynamic_context(user_query, max_qa=6)
    contents_text = f"{dynamic_kb}\n\n=== SOALAN PENGGUNA ===\n{user_query}"

    # Use gemini-3.6-flash as primary model for instant ~3 second responses
    models_to_try = [
        "gemini-3.6-flash",
        "gemini-flash-latest"
    ]

    for model_name in models_to_try:
        try:
            start_t = time.time()
            res = client.models.generate_content(
                model=model_name,
                contents=contents_text,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTIONS,
                    temperature=0.2,
                    max_output_tokens=400
                )
            )
            elapsed = time.time() - start_t
            if res and res.text:
                print(f"[DEBUG Gemini Speed] Model {model_name} responded in {elapsed:.2f}s")
                return res.text.strip()
        except Exception:
            continue

    return None

if __name__ == "__main__":
    test_queries = [
        "mcm mana nk dpt 2nd class upper uthm?",
        "berapa yuran fakulti fsktm untuk pelajar tempatan"
    ]
    for q in test_queries:
        print(f"\n====================\nQUERY: {q}\n====================")
        ans = query_gemini(q)
        print("ANSWER:\n", ans)
