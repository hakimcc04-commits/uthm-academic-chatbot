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

def retrieve_dynamic_context(user_query: str, max_qa: int = 15) -> str:
    load_data()
    
    query_lower = user_query.lower()
    query_words = set(re.findall(r"\w+", query_lower))
    stop_words = {
        "yang", "dan", "di", "ke", "ini", "itu", "saya", "nak", "bagaimana", "macam", "mana",
        "bila", "apa", "berapa", "is", "the", "in", "to", "what", "how", "uthm", "pelajar",
        "student", "ada", "boleh", "beri", "senarai", "list", "tentang", "mengenai", "bagi",
        "untuk", "for", "are", "can", "you", "give", "me"
    }
    meaningful_words = query_words - stop_words
    if not meaningful_words:
        meaningful_words = query_words

    lines = ["=== UTHM ACADEMIC KNOWLEDGE BASE (RELEVANT FACTS) ==="]

    # Special handling for awards query: guarantee ALL awards are included in context
    is_award_query = any(k in query_lower for k in ["anugerah", "award", "dekan", "diraja", "canselor", "pingat"])
    award_intents = {
        "anugerah_diraja", "anugerah_canselor", "anugerah_naib_canselor", "deans_award",
        "anugerah_alumni", "anugerah_tokoh_siswa", "anugerah_inovasi_ritec", "anugerah_psm"
    }

    scored_rows = []
    if _df_dataset is not None and not _df_dataset.empty:
        for idx, row in _df_dataset.iterrows():
            intent = str(row.get("intent", ""))
            q_text = (str(row.get("question", "")) + " " + intent).lower()
            q_words = set(re.findall(r"\w+", q_text))
            score = len(meaningful_words & q_words)
            if is_award_query and intent in award_intents:
                score += 10  # Massive priority boost for all award rows
            scored_rows.append((score, row))
        
        scored_rows.sort(key=lambda x: x[0], reverse=True)
        top_qa = scored_rows[:max_qa]
        
        lines.append("\n--- RELEVANT FREQUENTLY ASKED QUESTIONS ---")
        seen_questions = set()
        for score, row in top_qa:
            q = str(row.get("question", "")).strip()
            if q in seen_questions:
                continue
            seen_questions.add(q)
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
        lines.append("\n--- RELEVANT OFFICIAL DOCUMENTS & FORMS ---")
        matched_docs = []
        for idx, row in _df_docs.iterrows():
            doc_name = str(row.get("document_name", "")).strip()
            summary = str(row.get("summary", "")).strip()
            doc_text = (doc_name + " " + summary).lower()
            doc_words = set(re.findall(r"\w+", doc_text))
            doc_score = len(meaningful_words & doc_words)
            if doc_score > 0:
                matched_docs.append((doc_score, row))
        
        matched_docs.sort(key=lambda x: x[0], reverse=True)
        for score, row in matched_docs[:5]:
            doc_name = str(row.get("document_name", "")).strip()
            summary = str(row.get("summary", "")).strip()
            url = str(row.get("source_url", "")).strip()
            lines.append(f"Document: {doc_name}")
            lines.append(f"Summary: {summary}")
            if url and url != "nan":
                lines.append(f"URL: {url}")
            lines.append("-")

    return "\n".join(lines)

SYSTEM_INSTRUCTIONS = """Anda adalah Pembantu Pintar AI Akademik Rasmi Universiti Tun Hussein Onn Malaysia (UTHM Academic Chatbot).

Tugas utama anda:
1. Menjawab semua soalan akademik pengguna secara sangat tepat, teliti, mesra, berstruktur, dan kemas.
2. Memahami pelbagai variasi bahasa termasuk Bahasa Melayu pasar / slang / ejaan ringkas (contoh: 'mcm', 'nk', 'dpt', 'utk', '2nd class', 'gugur subjek', 'dekan', 'psm', 'pointer', 'ptptn').
3. Menggunakan UTHM Academic Knowledge Base yang disediakan sebagai rujukan fakta utama. Jangan mereka maklumat yang bertentangan dengan maklumat UTHM.
4. Menjawab mengikut bahasa yang digunakan oleh pengguna (Bahasa Melayu jika soalan BM/slang BM, English jika soalan Inggeris).
5. Sertakan pautan rasmi (Source URL / Document URL) jika relevan untuk memudahkan pengguna.
6. FORMAT JAWAPAN (SANGAT PENTING):
   - Mulakan dengan TAJUK HURUF BESAR (UPPERCASE) beserta ikon/emoji yang bersesuaian di hadapan (contoh: 🎓 **PANDUAN PINDAH KREDIT UTHM**).
   - Gunakan bullet points kemas dengan ikon menarik (📌, 📍, 📝, 💡, ⚖️, 🔗, ⚠️).
   - Tebalkan kata kunci penting menggunakan format Markdown standard (**kata kunci**). JANGAN sesekali gunakan tag HTML mentah seperti <b> atau <i>.
7. GAYA JAWAPAN LENGKAP TETAPI PADAT & RINGKAS (CONCISE YET COMPREHENSIVE):
   - Jika pengguna meminta senarai (contoh: senarai anugerah, senarai dokumen, senarai peraturan):
     • Senaraikan KESEMUA perkara tanpa tertinggal satu pun (contoh untuk anugerah: Anugerah Diraja, Anugerah Canselor, Anugerah Naib Canselor, Anugerah Dekan, Anugerah Alumni, Anugerah Tokoh Siswa, Pingat Inovasi RITEC, Anugerah PSM).
     • Berikan huraian yang RINGKAS, PADAT, dan TEPAT (1 hingga 2 baris sahaja untuk setiap anugerah/perkara) yang menyatakan syarat utama.
     • Elakkan huraian yang terlalu panjang lebar atau meleret-leret supaya mesej kemas, mudah dibaca sekilas pandang, dan muat dalam satu mesej Telegram tanpa terpotong.
8. PENTING - SOALAN BUKAN AKADEMIK / DI LUAR SKOP: Jika soalan pengguna JELAS TIDAK BERKAITAN dengan hal ehwal akademik universiti (contohnya soalan tentang makanan seperti pizza, ekonomi negara umum, politik, sukan, gosip, cuaca, resepi masakan, atau topik bukan universiti), nyatakan dengan sopan bahawa anda adalah Pembantu Pintar Khusus untuk Akademik UTHM sahaja, dan jemput pengguna bertanya tentang perkara akademik universiti.
"""

def query_gemini(user_query: str, context: dict = None) -> str:
    client = get_client()
    if not client:
        return None

    dynamic_kb = retrieve_dynamic_context(user_query, max_qa=15)
    contents_text = f"{dynamic_kb}\n\n=== SOALAN PENGGUNA ===\n{user_query}"

    # Use gemini-flash-lite-latest for instant ~2 second responses with fallback to gemini-flash-latest
    models_to_try = [
        "gemini-flash-lite-latest",
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
                    max_output_tokens=1500
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
