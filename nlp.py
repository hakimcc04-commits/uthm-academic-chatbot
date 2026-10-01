from semantic_engine import semantic_engine
from gemini_engine import query_gemini
import pandas as pd
import joblib
import re
from pathlib import Path
from difflib import SequenceMatcher

model = joblib.load("academic_chatbot_model.pkl")
df = pd.read_csv("academic_chatbot_dataset.csv")
BASE_DIR = Path(__file__).resolve().parent

last_prediction = {
    "intent": None,
    "confidence": None
}

response_en_map = (
    df.drop_duplicates("intent")
      .set_index("intent")["response_en"]
      .to_dict()
)

response_bm_map = (
    df.drop_duplicates("intent")
      .set_index("intent")["response_bm"]
      .to_dict()
)

source_map = (
    df.drop_duplicates("intent")
      .set_index("intent")["source_url"]
      .to_dict()
)

conversation_context = {
    "last_intent": None,
    "last_document": None,
    "last_document_file": None,
    "last_language": "en",
    "last_suggestions": [],
    "ui_kind": None,
    "ui_choices": [],
}

FOLLOW_UP_OPTIONS = {
    "add_drop_course": [
        {"key": "1", "en": "Add/drop period", "bm": "Tempoh tambah/gugur"},
        {"key": "2", "en": "Course registration rules", "bm": "Peraturan pendaftaran kursus"},
    ],
    "course_registration": [
        {"key": "1", "en": "Course registration process", "bm": "Proses pendaftaran kursus"},
        {"key": "2", "en": "Add/drop course", "bm": "Tambah/gugur kursus"},
        {"key": "3", "en": "Academic calendar", "bm": "Kalendar akademik"},
    ],
    "academic_calendar": [
        {"key": "1", "en": "Semester dates", "bm": "Tarikh semester"},
        {"key": "2", "en": "Examination week", "bm": "Minggu peperiksaan"},
        {"key": "3", "en": "University holidays", "bm": "Cuti universiti"},
    ],
    "final_exam": [
        {"key": "1", "en": "Exam timetable", "bm": "Jadual peperiksaan"},
        {"key": "2", "en": "Examination week", "bm": "Minggu peperiksaan"},
        {"key": "3", "en": "Final examination information", "bm": "Maklumat peperiksaan akhir"},
    ],
    "graduation": [
        {"key": "1", "en": "Graduation eligibility", "bm": "Kelayakan graduasi"},
        {"key": "2", "en": "Convocation information", "bm": "Maklumat konvokesyen"},
    ],
    "fee_payment": [
        {"key": "1", "en": "Tuition fee details", "bm": "Maklumat yuran pengajian"},
        {"key": "2", "en": "Payment methods", "bm": "Kaedah bayaran"},
    ],
    "cgpa_gpa": [
        {"key": "1", "en": "Academic status", "bm": "Status akademik"},
        {"key": "2", "en": "Academic regulation", "bm": "Peraturan akademik"},
    ],
    "academic_regulation": [
        {"key": "1", "en": "GPA / CGPA", "bm": "GPA / CGPA"},
        {"key": "2", "en": "Course registration rules", "bm": "Peraturan pendaftaran kursus"},
    ],
}


def set_ui_choices(kind, choices):
    conversation_context["ui_kind"] = kind
    conversation_context["ui_choices"] = choices or []


def get_ui_payload():
    return {
        "kind": conversation_context.get("ui_kind"),
        "choices": conversation_context.get("ui_choices") or [],
        "language": conversation_context.get("last_language", "en"),
    }


def after_answer_choices(language="en"):
    if language == "bm":
        return [
            {"key": "ask", "en": "Ask a new question", "bm": "Soalan baharu"},
            {"key": "docs", "en": "View documents", "bm": "Lihat dokumen"},
        ]
    return [
        {"key": "ask", "en": "Ask a new question", "bm": "Soalan baharu"},
        {"key": "docs", "en": "View documents", "bm": "Lihat dokumen"},
    ]


def yesno_choices():
    return [
        {"key": "yes", "en": "Yes, show options", "bm": "Ya, tunjuk pilihan"},
        {"key": "ask", "en": "Ask a new question", "bm": "Soalan baharu"},
    ]

follow_up_en_map = {
    "course_registration": "Do you want to know about add/drop course or academic calendar?",
    "add_drop_course": "Do you want to know the add/drop period or course registration rules?",
    "academic_calendar": "Do you want to know about semester dates or examination weeks?",
    "final_exam": "Do you want to check academic calendar or examination information?",
    "cgpa_gpa": "Do you want to ask about academic status or grading system?",
    "academic_regulation": "Do you want to ask about GPA, CGPA, or course registration rules?",
    "graduation": "Do you want to know about graduation eligibility or convocation information?",
    "fee_payment": "Do you want to check tuition fee details or payment methods?",
    "contact_ppa": "Do you want contact information for another university department?",
    "student_bulletin": "Do you want to check university announcements or academic notices?"
}

follow_up_bm_map = {
    "course_registration": "Adakah anda mahu tahu tentang tambah/gugur kursus atau kalendar akademik?",
    "add_drop_course": "Adakah anda mahu tahu tempoh tambah/gugur atau peraturan pendaftaran kursus?",
    "academic_calendar": "Adakah anda mahu tahu tentang tarikh semester atau minggu peperiksaan?",
    "final_exam": "Adakah anda mahu semak kalendar akademik atau maklumat peperiksaan?",
    "cgpa_gpa": "Adakah anda mahu bertanya tentang status akademik atau sistem gred?",
    "academic_regulation": "Adakah anda mahu bertanya tentang GPA, CGPA, atau peraturan pendaftaran kursus?",
    "graduation": "Adakah anda mahu tahu tentang kelayakan graduasi atau maklumat konvokesyen?",
    "fee_payment": "Adakah anda mahu semak maklumat yuran pengajian atau kaedah bayaran?",
    "contact_ppa": "Adakah anda mahu maklumat hubungan jabatan universiti yang lain?",
    "student_bulletin": "Adakah anda mahu semak pengumuman universiti atau hebahan akademik?"
}

yes_words = ["yes", "y", "yeah", "sure", "ok", "okay", "boleh", "ya", "yup"]

documents_df = pd.read_csv("documents.csv")
web_sources_path = BASE_DIR / "academic_web_sources.csv"
if web_sources_path.exists():
    web_sources_df = pd.read_csv(web_sources_path)
    documents_df = pd.concat([documents_df, web_sources_df], ignore_index=True, sort=False)
else:
    web_sources_df = pd.DataFrame()

def resolve_document_path(file_path):
    if pd.isna(file_path) or not str(file_path).strip() or str(file_path).strip().lower() == "nan":
        return None

    path = Path(str(file_path).strip())
    if not path.is_absolute():
        path = BASE_DIR / path

    return path if path.exists() else None

def get_last_document_file():
    file_path = conversation_context.get("last_document_file")
    resolved_path = resolve_document_path(file_path)

    if resolved_path is None:
        return None

    return resolved_path

def get_document_summary(row, language):
    document_name = str(row.get("document_name", ""))
    summary = str(row.get("summary", ""))
    if document_name.startswith("Tuition Fee Structure "):
        faculty_code = document_name.replace("Tuition Fee Structure ", "").strip()
        if language != "bm":
            return (
                f"International undergraduate tuition fee structure for {faculty_code} "
                "session 2025/2026, including the total tuition fee for each programme."
            )

        return (
            f"Dokumen yuran pengajian antarabangsa sesi 2025/2026 untuk {faculty_code}, "
            "termasuk jumlah yuran setiap program."
        )

    en_summaries = {
        "Academic Calendar": "This academic calendar document for the 2026/2027 session contains semester dates, lecture weeks, holidays, revision week and examination weeks.",
        "Academic Regulation": "This document contains academic regulations, course registration rules, add/drop procedures, GPA, CGPA and examination regulations.",
        "Final Examination Information": "This page provides final examination information, examination timetable and examination procedures.",
        "Graduation Information": "This page provides graduation and convocation information for UTHM students.",
        "Tuition Fee Information": "This page provides tuition fee and payment information for students.",
        "PPA Contact Directory": "This page provides official contact information for the Academic Management Office.",
    }

    if language != "bm":
        return en_summaries.get(document_name, summary)

    bm_summaries = {
        "Academic Calendar": "Dokumen ini mengandungi tarikh semester, minggu kuliah, cuti, minggu ulang kaji dan minggu peperiksaan.",
        "Academic Regulation": "Dokumen ini mengandungi peraturan akademik, pendaftaran kursus, prosedur tambah/gugur, GPA, CGPA dan peraturan peperiksaan.",
        "Final Examination Information": "Halaman ini menyediakan maklumat peperiksaan akhir, jadual peperiksaan dan prosedur peperiksaan.",
        "Graduation Information": "Halaman ini menyediakan maklumat graduasi dan konvokesyen untuk pelajar UTHM.",
        "Tuition Fee Information": "Halaman ini menyediakan maklumat yuran pengajian dan bayaran untuk pelajar.",
        "PPA Contact Directory": "Halaman ini menyediakan maklumat hubungan rasmi Pejabat Pengurusan Akademik.",
    }

    return bm_summaries.get(document_name, summary)

def get_document_display_name(document_name, language):
    if language != "bm":
        return document_name

    if str(document_name).startswith("Tuition Fee Structure "):
        faculty_code = str(document_name).replace("Tuition Fee Structure ", "").strip()
        return f"Struktur Yuran Pengajian {faculty_code}"

    bm_names = {
        "Academic Calendar": "Kalendar Akademik",
        "Academic Calendar 2025/2026 (English)": "Kalendar Akademik 2025/2026 (English)",
        "Academic Calendar 2025/2026 (BM)": "Kalendar Akademik 2025/2026 (BM)",
        "Takwim Mesyuarat Senat 2026": "Takwim Mesyuarat Senat 2026",
        "Takwim Mesyuarat JPA 2026": "Takwim Mesyuarat JPA 2026",
        "Jadual Kerja Pelajar Semester I 2026/2027": "Jadual Kerja Pelajar Semester I 2026/2027",
        "Jadual Kerja Pelajar Semester Khas 2026/2027": "Jadual Kerja Pelajar Semester Khas 2026/2027",
        "Manual Pendaftaran Kursus SMAP AUTOREG": "Manual Pendaftaran Kursus SMAP AUTOREG",
        "Academic Regulation": "Peraturan Akademik",
        "Final Examination Information": "Maklumat Peperiksaan Akhir",
        "Graduation Information": "Maklumat Graduasi",
        "Tuition Fee Information": "Maklumat Yuran Pengajian",
        "PPA Contact Directory": "Direktori Hubungan PPA",
    }

    return bm_names.get(document_name, document_name)

SHORT_FORM_MAP = {
    "berpa": "berapa",
    "brapa": "berapa",
    "bape": "berapa",
    "ape": "apa",
    "mcm": "macam",
    "cm": "macam",
    "mna": "mana",
    "mnn": "mana",
    "mn": "mana",
    "nk": "nak",
    "nakkk": "nak",
    "dftar": "daftar",
    "dftr": "daftar",
    "daft": "daftar",
    "rgister": "register",
    "regster": "register",
    "registerr": "register",
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
    "pengjian": "pengajian",
    "pengajain": "pengajian",
    "akdemik": "akademik",
    "akademk": "akademik",
    "klander": "kalendar",
    "kalender": "kalendar",
    "calender": "calendar",
    "doc": "document",
    "docs": "document",
    "dokument": "dokumen",
    "dokumn": "dokumen",
    "transkrp": "transkrip",
    "smap": "smap",
    "jadual": "jadual",
    "jdual": "jadual",
    "jdual": "jadual",
    "peperiksaan": "peperiksaan",
    "exam": "exam",
    "exm": "exam",
    "xam": "exam",
    "finals": "final",
    "konvo": "konvokesyen",
    "grad": "graduation",
    "graduasi": "graduasi",
    "yuran": "yuran",
    "yrn": "yuran",
    "fee": "fee",
    "fees": "fee",
    "bayr": "bayar",
    "byr": "bayar",
    "tgguh": "tangguh",
    "tanggoh": "tangguh",
    "ppa": "ppa",
    "cgpa": "cgpa",
    "gpa": "gpa",
    "anugrah": "anugerah",
    "angrah": "anugerah",
    "anugra": "anugerah",
    "nc": "naib canselor",
}

def clean_text(text):
    text = str(text).lower()
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    words = [SHORT_FORM_MAP.get(word, word) for word in text.strip().split()]
    return " ".join(words)

df["clean_question"] = df["question"].apply(clean_text)
tuition_fees_path = BASE_DIR / "tuition_fees.csv"
tuition_df = pd.read_csv(tuition_fees_path) if tuition_fees_path.exists() else pd.DataFrame()

if not tuition_df.empty:
    tuition_df["clean_program_name"] = tuition_df["program_name"].apply(clean_text)
    tuition_df["clean_faculty_code"] = tuition_df["faculty_code"].astype(str).str.lower()

TUITION_PROGRAM_CODES = (
    set(tuition_df["program_code"].astype(str).str.lower())
    if not tuition_df.empty
    else set()
)
TUITION_FACULTY_CODES = (
    set(tuition_df["faculty_code"].astype(str).str.lower())
    if not tuition_df.empty
    else set()
)

EXACT_QUESTION_MAP = {
    row["clean_question"]: row
    for _, row in df.iterrows()
}

DATASET_MATCH_THRESHOLD = 0.65
MODEL_CONFIDENCE_THRESHOLD = 0.45
SUGGESTION_MATCH_THRESHOLD = 0.45

ACADEMIC_KEYWORDS = {
    "akademik", "academic", "kursus", "course", "subjek", "subject",
    "daftar", "register", "registration", "yuran", "fee", "tuition",
    "exam", "peperiksaan", "jadual", "schedule", "calendar", "kalendar",
    "gpa", "cgpa", "graduation", "graduasi", "konvokesyen", "convocation",
    "ppa", "smap", "muet", "ptptn", "dokumen", "document", "borang",
    "form", "sijil", "certificate", "transkrip", "transcript", "surat",
    "pengesahan", "verification", "pengajian", "semester", "kaunter",
    "counter", "kemasukan", "admission", "program", "kuliah", "lecture",
    "senat", "senate", "jpa", "spak", "tcis", "library", "anugerah", "award", "diraja", "canselor", "alumni", "psm", "ritec", "tokoh", "pingat"
}

def token_overlap_ratio(user_text, dataset_text):
    user_tokens = set(user_text.split())
    dataset_tokens = set(dataset_text.split())

    if not user_tokens or not dataset_tokens:
        return 0

    return len(user_tokens & dataset_tokens) / len(user_tokens)

def find_dataset_match(cleaned_input):
    if cleaned_input in EXACT_QUESTION_MAP:
        return EXACT_QUESTION_MAP[cleaned_input], 1.0

    best_row = None
    best_score = 0
    input_tokens = set(cleaned_input.split())

    for _, row in df.iterrows():
        dataset_question = row["clean_question"]
        sequence_score = SequenceMatcher(None, cleaned_input, dataset_question).ratio()
        overlap_score = token_overlap_ratio(cleaned_input, dataset_question)
        score = (sequence_score * 0.75) + (overlap_score * 0.25)
        dataset_tokens = set(dataset_question.split())

        if len(input_tokens) >= 2 and input_tokens.issubset(dataset_tokens):
            score = max(score, 0.86)

        if score > best_score:
            best_score = score
            best_row = row

    if best_score >= DATASET_MATCH_THRESHOLD:
        return best_row, best_score

    return None, best_score

def score_dataset_question(cleaned_input, dataset_question):
    input_tokens = set(cleaned_input.split())
    dataset_tokens = set(dataset_question.split())
    sequence_score = SequenceMatcher(None, cleaned_input, dataset_question).ratio()
    overlap_score = token_overlap_ratio(cleaned_input, dataset_question)
    score = (sequence_score * 0.75) + (overlap_score * 0.25)

    if len(input_tokens) >= 2 and input_tokens.issubset(dataset_tokens):
        score = max(score, 0.86)

    return score

def find_dataset_suggestions(cleaned_input, limit=3):
    suggestions = []
    seen_intents = set()

    for _, row in df.iterrows():
        score = score_dataset_question(cleaned_input, row["clean_question"])

        if score < SUGGESTION_MATCH_THRESHOLD:
            continue

        intent = row["intent"]
        if intent in seen_intents:
            continue

        suggestions.append((score, row))
        seen_intents.add(intent)

    suggestions.sort(key=lambda item: item[0], reverse=True)
    return [row for _, row in suggestions[:limit]]

def is_academic_like(cleaned_input):
    tokens = set(cleaned_input.split())
    return bool(tokens & (ACADEMIC_KEYWORDS | TUITION_PROGRAM_CODES | TUITION_FACULTY_CODES))

def format_fee_amount(amount):
    amount = str(amount).strip()
    return amount if amount.startswith("RM") else f"RM {amount}"

def tuition_query_has_fee_word(cleaned_input):
    fee_words = [
        "yuran", "fee", "tuition", "pengajian", "bayaran",
        "berapa", "amount", "total", "cost", "kos"
    ]
    return contains_any(cleaned_input, fee_words)

def build_single_tuition_response(row, user_input):
    language = detect_language(user_input)
    program_code = str(row["program_code"])
    faculty_code = str(row["faculty_code"])
    program_name = str(row["program_name"])
    duration = str(row.get("duration_semesters", "")).strip()
    amount = format_fee_amount(row["total_tuition_fee_rm"])
    source_file = str(row.get("source_file", "")).strip()

    conversation_context["last_intent"] = "tuition_fee_program"
    conversation_context["last_language"] = language
    conversation_context["last_suggestions"] = []

    duration_line_bm = f"Tempoh pengajian: {duration} semester\n" if duration else ""
    duration_line_en = f"Study duration: {duration} semesters\n" if duration else ""
    set_ui_choices("after", after_answer_choices(language))

    if language == "bm":
        return (
            f"Jumlah yuran pengajian bagi program {program_code} ({faculty_code}) ialah {amount}.\n\n"
            f"Program: {program_name}\n"
            f"{duration_line_bm}"
            f"Sumber dokumen: {source_file}\n\n"
            f"Jika anda mahu fail PDF, taip: dokumen yuran {faculty_code}"
        )

    return (
        f"The total tuition fee for {program_code} ({faculty_code}) is {amount}.\n\n"
        f"Program: {program_name}\n"
        f"{duration_line_en}"
        f"Source document: {source_file}\n\n"
        f"To receive the PDF file, type: {faculty_code} fee document"
    )

def build_faculty_tuition_response(faculty_code, rows, user_input):
    language = detect_language(user_input)
    rows = rows.sort_values("program_code")

    conversation_context["last_intent"] = "tuition_fee_program"
    conversation_context["last_language"] = language
    conversation_context["last_suggestions"] = []

    lines = [
        f"- {row['program_code']}: {format_fee_amount(row['total_tuition_fee_rm'])}"
        for _, row in rows.iterrows()
    ]
    source_file = str(rows.iloc[0].get("source_file", "")).strip()
    set_ui_choices("after", after_answer_choices(language))

    if language == "bm":
        return (
            f"Ringkasan yuran pengajian {faculty_code}:\n\n"
            + "\n".join(lines)
            + f"\n\nSumber dokumen: {source_file}\n"
            + f"Taip yuran <kod program> untuk detail, contoh: yuran {rows.iloc[0]['program_code']}.\n"
            + f"Untuk fail PDF, taip: dokumen yuran {faculty_code}"
        )

    return (
        f"Tuition fee summary for {faculty_code}:\n\n"
        + "\n".join(lines)
        + f"\n\nSource document: {source_file}\n"
        + f"Type fee <programme code> for details, for example: fee {rows.iloc[0]['program_code']}.\n"
        + f"For the PDF file, type: {faculty_code} fee document"
    )


def build_current_tuition_document_response(user_input):
    """Route exact fee requests to the current official local/overseas PDFs."""
    language = detect_language(user_input)
    conversation_context["last_intent"] = "tuition_fee_document"
    conversation_context["last_language"] = language
    conversation_context["last_suggestions"] = []
    set_ui_choices(
        "after",
        [
            {
                "key": "fees",
                "en": "Open 2026/2027 fee documents",
                "bm": "Buka dokumen yuran 2026/2027",
            },
            {"key": "menu", "en": "Main menu", "bm": "Menu utama"},
        ],
    )

    if language == "bm":
        return (
            "Untuk kadar yuran rasmi sesi 2026/2027 bagi pelajar tempatan dan "
            "antarabangsa, sila buka dokumen yuran di bawah. Pilih fakulti atau "
            "program Sarjana, PhD, atau Diploma anda untuk jadual lengkap."
        )

    return (
        "For the official 2026/2027 local and international tuition rates, "
        "open the fee documents below and select your faculty or postgraduate "
        "or diploma programme for the complete table."
    )


def search_tuition_fee(user_input):
    cleaned_input = clean_text(user_input)
    tokens = set(cleaned_input.split())
    has_fee_word = tuition_query_has_fee_word(cleaned_input)
    program_tokens = tokens & TUITION_PROGRAM_CODES
    faculty_tokens = tokens & TUITION_FACULTY_CODES
    current_rate_terms = {
        "tempatan", "local", "antarabangsa", "international",
        "2026", "2027", "terkini", "current",
    }

    # The historical CSV only contains earlier international summaries. Direct
    # exact rate requests to the new official PDFs rather than returning an
    # outdated amount.
    if (program_tokens or faculty_tokens) and (
        has_fee_word or bool(tokens & current_rate_terms)
    ):
        last_prediction["intent"] = "tuition_fee_document"
        last_prediction["confidence"] = 1.0
        return build_current_tuition_document_response(user_input)

    if tuition_df.empty:
        return None

    if program_tokens:
        program_code = sorted(program_tokens)[0].upper()
        matched = tuition_df[tuition_df["program_code"].astype(str).str.casefold() == program_code.casefold()]
        if not matched.empty and (has_fee_word or len(tokens) <= 4 or faculty_tokens):
            last_prediction["intent"] = "tuition_fee_program"
            last_prediction["confidence"] = 1.0
            return build_single_tuition_response(matched.iloc[0], user_input)

    if faculty_tokens and has_fee_word:
        faculty_code = sorted(faculty_tokens)[0].upper()
        matched = tuition_df[tuition_df["faculty_code"].astype(str).str.casefold() == faculty_code.casefold()]
        if not matched.empty:
            last_prediction["intent"] = "tuition_fee_faculty"
            last_prediction["confidence"] = 1.0
            return build_faculty_tuition_response(faculty_code, matched, user_input)

    if not has_fee_word:
        return None

    best_row = None
    best_score = 0

    for _, row in tuition_df.iterrows():
        score = score_dataset_question(cleaned_input, row["clean_program_name"])
        if score > best_score:
            best_score = score
            best_row = row

    if best_row is not None and best_score >= 0.68:
        last_prediction["intent"] = "tuition_fee_program"
        last_prediction["confidence"] = best_score
        return build_single_tuition_response(best_row, user_input)

    return None

def is_unsupported_subsidy_fee_query(cleaned_input):
    fee_words = {"yuran", "fee", "tuition", "pengajian", "bayaran"}
    subsidy_words = {
        "subsidi", "subsidy", "subsidized", "subsidised",
        "kerajaan", "government", "ditolak", "tolak", "after"
    }
    tokens = set(cleaned_input.split())
    return bool(tokens & fee_words) and bool(tokens & subsidy_words)

def build_missing_official_source_response(user_input):
    language = detect_language(user_input)
    last_prediction["intent"] = None
    last_prediction["confidence"] = 0
    set_ui_choices("after", after_answer_choices(language))

    if language == "bm":
        return (
            "Maaf, saya belum mempunyai sumber rasmi yang cukup untuk menjawab soalan itu dengan tepat.\n\n"
            "Untuk maklumat fakta seperti yuran selepas ditolak subsidi kerajaan, sistem perlu ada "
            "dokumen atau data rasmi terlebih dahulu. Jika dokumen rasmi dimasukkan ke dalam sistem, "
            "saya boleh jawab berdasarkan sumber tersebut."
        )

    return (
        "Sorry, I do not have enough official source data to answer that accurately.\n\n"
        "For factual information such as tuition fees after government subsidy, the system needs "
        "an official document or verified data first. Once the official data is added, I can answer "
        "based on that source."
    )

def build_suggestion_response(suggestions, user_input):
    language = detect_language(user_input)
    conversation_context["last_suggestions"] = [row.to_dict() for row in suggestions]
    conversation_context["last_intent"] = "suggestion_request"
    conversation_context["last_language"] = language
    last_prediction["intent"] = "suggestion_request"
    last_prediction["confidence"] = max(
        score_dataset_question(clean_text(user_input), row["clean_question"])
        for row in suggestions
    )

    if language == "bm":
        lines = ["Saya belum pasti soalan anda. Mungkin maksud anda:\n"]
        for index, row in enumerate(suggestions, start=1):
            lines.append(f"{index}. {row['question']}")
        lines.append("\nSila ketik nombor di bawah, atau tulis semula soalan dengan lebih jelas.")
        set_ui_choices(
            "suggestion",
            [{"key": str(index), "en": row["question"], "bm": row["question"]} for index, row in enumerate(suggestions, start=1)],
        )
        return "\n".join(lines)

    lines = ["I am not fully sure what you mean. Did you mean:\n"]
    for index, row in enumerate(suggestions, start=1):
        lines.append(f"{index}. {row['question']}")
    lines.append("\nPlease tap a number below, or rephrase your question.")
    set_ui_choices(
        "suggestion",
        [{"key": str(index), "en": row["question"], "bm": row["question"]} for index, row in enumerate(suggestions, start=1)],
    )
    return "\n".join(lines)

def detect_language(text):

    bm_words = [
        "macam",
        "mana",
        "nak",
        "apa",
        "apakah",
        "boleh",
        "tak",
        "ke",
        "kalau",
        "kalu",
        "beri",
        "bagi",
        "senaraikan",
        "semua",
        "soalan",
        "jawapan",
        "sila",
        "tolong",
        "bantuan",
        "terima",
        "kasih",
        "hendak",
        "saya",
        "bolehkah",
        "adakah",
        "siapa",
        "pukul",
        "bagaimana",
        "bila",
        "kursus",
        "subjek",
        "jadual",
        "peperiksaan",
        "graduasi",
        "yuran",
        "pendaftaran",
        "peraturan",
        "akademik",
        "permohonan",
        "kemasukan",
        "kaunter",
        "perkhidmatan",
        "tawaran",
        "lepasan",
        "bekerja",
        "sepenuh",
        "masa",
        "kata",
        "laluan",
        "hubungi",
        "alamat",
        "emel",
        "faks",
        "kuliah",
        "peperiksaan",
        "muet",
        "graduan",
        "ptptn",
        "pengecualian",
        "sijil",
        "transkrip",
        "penganugerahan",
        "gunasama",
        "guna",
        "senat",
        "syarat",
        "antarabangsa",
        "warganegara",
        "tarik",
        "diri",
        "berhenti",
        "hutang",
        "kesihatan",
        "surat",
        "pengesahan",
        "aplikasi"
    ]

    text = text.lower()

    for word in bm_words:
        if word in text:
            return "bm"

    return "en"

def contains_any(text, keywords):
    return any(keyword in text for keyword in keywords)

def build_response_from_row(row, user_input):

    language = detect_language(user_input)
    cleaned_input = clean_text(user_input)
    if cleaned_input.isdigit() or cleaned_input in yes_words:
        language = conversation_context.get("last_language", language)

    conversation_context["last_suggestions"] = []

    if language == "bm":
        response = row.get("response_bm", "")
    else:
        response = row.get("response_en", "")

    if not response:
        response = "Maaf, saya tidak mempunyai maklumat untuk soalan ini." if language == "bm" else "Sorry, I do not have information for this question yet."

    source_url = row.get("source_url", "")

    if source_url:
        if language == "bm":
            response += f"\n\nUntuk maklumat lanjut, sila layari:\n{source_url}"
        else:
            response += f"\n\nFor more information, please visit:\n{source_url}"

    if language == "bm":
        follow_up = follow_up_bm_map.get(
            row.get("intent"),
            "Adakah anda mahu bertanya soalan akademik yang lain?"
        )
    else:
        follow_up = follow_up_en_map.get(
            row.get("intent"),
            "Do you want to ask another academic question?"
        )

    response += f"\n\n{follow_up}"

    conversation_context["last_intent"] = row.get("intent")
    conversation_context["last_language"] = language

    if row.get("intent") in FOLLOW_UP_OPTIONS:
        set_ui_choices("yesno", yesno_choices())
    else:
        set_ui_choices("after", after_answer_choices(language))

    return response

def build_response(intent, user_input):
    intent_rows = df[df["intent"] == intent]

    if not intent_rows.empty:
        return build_response_from_row(intent_rows.iloc[0], user_input)

    language = detect_language(user_input)
    return "Maaf, saya tidak mempunyai maklumat untuk soalan ini." if language == "bm" else "Sorry, I do not have information for this question yet."

def get_option_message(last_intent, language="en"):
    options = FOLLOW_UP_OPTIONS.get(last_intent)
    if not options:
        set_ui_choices("after", after_answer_choices(language))
        if language == "bm":
            return "Baik. Sila taip soalan akademik seterusnya, atau ketik butang di bawah."
        return "Sure. Please type your next academic question, or tap a button below."

    set_ui_choices("followup", options)
    if language == "bm":
        lines = ["Baik. Anda boleh pilih salah satu pilihan ini:\n"]
        for option in options:
            lines.append(f"{option['key']}. {option['bm']}")
        lines.append("\nSila ketik nombor di bawah.")
        return "\n".join(lines)

    lines = ["Sure. You can choose one of these options:\n"]
    for option in options:
        lines.append(f"{option['key']}. {option['en']}")
    lines.append("\nPlease tap a number below.")
    return "\n".join(lines)

def handle_context_follow_up(cleaned_input, last_intent, user_input):
    if last_intent is None:
        return None

    if cleaned_input in yes_words:
        language = conversation_context.get("last_language", detect_language(user_input))
        return get_option_message(last_intent, language)

    if last_intent == "add_drop_course":
        if cleaned_input == "1":
            return build_response("add_drop_period", user_input)

        if cleaned_input == "2":
            return build_response("course_registration_rules", user_input)

        if contains_any(cleaned_input, ["period", "date", "when", "timeline", "schedule"]):
            return build_response("add_drop_period", user_input)

        if contains_any(cleaned_input, ["rule", "rules", "regulation", "procedure", "requirement"]):
            return build_response("course_registration_rules", user_input)

    if last_intent == "course_registration":
        if cleaned_input == "1":
            return build_response("course_registration", user_input)

        if cleaned_input == "2":
            return build_response("add_drop_course", user_input)

        if cleaned_input == "3":
            return build_response("academic_calendar", user_input)

        if contains_any(cleaned_input, ["add", "drop", "change", "subject", "course correction"]):
            return build_response("add_drop_course", user_input)

        if contains_any(cleaned_input, ["calendar", "date", "when", "semester"]):
            return build_response("academic_calendar", user_input)

        if contains_any(cleaned_input, ["process", "register", "registration", "how"]):
            return build_response("course_registration", user_input)

    if last_intent == "academic_calendar":
        if cleaned_input == "1":
            return build_response("academic_calendar", user_input)

        if cleaned_input == "2":
            return build_response("exam_week", user_input)

        if cleaned_input == "3":
            return build_response("academic_calendar", user_input)

        if contains_any(cleaned_input, ["exam", "examination", "final"]):
            return build_response("exam_week", user_input)

        if contains_any(cleaned_input, ["semester", "start", "begin", "date"]):
            return build_response("academic_calendar", user_input)

        if contains_any(cleaned_input, ["holiday", "break", "cuti"]):
            return build_response("academic_calendar", user_input)

    if last_intent == "final_exam":
        if cleaned_input == "1":
            return build_response("final_exam", user_input)

        if cleaned_input == "2":
            return build_response("exam_week", user_input)

        if cleaned_input == "3":
            return build_response("ppa_final_exam_schedule", user_input)

        if contains_any(cleaned_input, ["timetable", "schedule"]):
            return build_response("final_exam", user_input)

        if contains_any(cleaned_input, ["week", "date", "when"]):
            return build_response("exam_week", user_input)

        if contains_any(cleaned_input, ["information", "info", "guideline"]):
            return build_response("final_exam", user_input)

    if last_intent == "graduation":
        if cleaned_input == "1":
            return build_response("graduation_eligibility", user_input)

        if cleaned_input == "2":
            return build_response("convocation", user_input)

        if contains_any(cleaned_input, ["eligibility", "eligible", "requirement", "graduate"]):
            return build_response("graduation_eligibility", user_input)

        if contains_any(cleaned_input, ["convocation", "ceremony"]):
            return build_response("graduation", user_input)

    if last_intent == "fee_payment":
        if cleaned_input == "1":
            return build_response("fee_payment", user_input)

        if cleaned_input == "2":
            return build_response("fee_payment", user_input)

        if contains_any(cleaned_input, ["tuition", "fee", "amount", "details"]):
            return build_response("fee_payment", user_input)

        if contains_any(cleaned_input, ["pay", "payment", "method", "online"]):
            return build_response("fee_payment", user_input)

    if last_intent == "cgpa_gpa":
        if cleaned_input == "1":
            return build_response("academic_status", user_input)
        if cleaned_input == "2":
            return build_response("academic_regulation", user_input)
        if contains_any(cleaned_input, ["status", "kedudukan"]):
            return build_response("academic_status", user_input)
        if contains_any(cleaned_input, ["regulation", "peraturan", "rule"]):
            return build_response("academic_regulation", user_input)

    if last_intent == "academic_regulation":
        if cleaned_input == "1":
            return build_response("cgpa_gpa", user_input)
        if cleaned_input == "2":
            return build_response("course_registration_rules", user_input)
        if contains_any(cleaned_input, ["gpa", "cgpa", "grade"]):
            return build_response("cgpa_gpa", user_input)
        if contains_any(cleaned_input, ["register", "registration", "pendaftaran"]):
            return build_response("course_registration_rules", user_input)

    return None

def search_document(user_input):
    cleaned_input = clean_text(user_input)
    language = detect_language(user_input)

    document_words = [
        "document", "file", "pdf", "link", "download",
        "dokumen", "fail", "muat turun", "rujukan",
        "borang", "form", "sijil", "transkrip",
        "certificate", "transcript", "panduan", "guideline",
        "kertas kerja", "senat", "jpa", "pak", "template",
        "templat", "memo", "cv"
    ]

    if not any(re.search(r'\b' + re.escape(word) + r'\b', cleaned_input) for word in document_words):
        return None

    # For high-specificity student services, use the official PPA page rather
    # than allowing a broad navigation-page summary to win the document match.
    if set(cleaned_input.split()) & {"transkrip", "transcript", "certificate", "sijil"}:
        official_source_response = search_official_web_source(user_input)
        if official_source_response:
            return official_source_response

    best_row = None
    best_score = 0

    for _, row in documents_df.iterrows():
        keywords = str(row["keywords"]).lower().split(",")

        for keyword in keywords:
            keyword = clean_text(keyword.strip())
            if not keyword:
                continue

            keyword_tokens = set(keyword.split())
            input_tokens = set(cleaned_input.split())
            overlap = len(keyword_tokens & input_tokens)
            score = overlap / max(len(keyword_tokens), 1)

            if keyword in cleaned_input:
                score += 1 if len(keyword_tokens) > 1 else 0.15

            coded_tokens = TUITION_PROGRAM_CODES | TUITION_FACULTY_CODES
            if (keyword_tokens & input_tokens & coded_tokens):
                score += 2.0

            score += min(len(keyword_tokens), 6) * 0.01

            if score > best_score:
                best_score = score
                best_row = row

    if best_row is not None and best_score >= 0.65:

        conversation_context["last_intent"] = "document_request"
        conversation_context["last_document"] = best_row["document_name"]
        conversation_context["last_document_file"] = best_row.get("file_path", "")
        conversation_context["last_language"] = language
        summary = get_document_summary(best_row, language)

        local_file = resolve_document_path(best_row.get("file_path", ""))
        source_url = str(best_row.get("source_url", "")).strip()
        source_line_bm = f"Sumber Rasmi:\n{source_url}\n\n" if source_url and not local_file else ""
        source_line_en = f"Official Source:\n{source_url}\n\n" if source_url and not local_file else ""

        if language == "bm":
            delivery_note = (
                "Saya akan hantar fail dokumen di sini."
                if local_file
                else "Fail lokal belum tersedia, sila guna pautan rasmi di bawah."
            )

            set_ui_choices(
                "yesno_doc",
                [
                    {"key": "yes", "en": "Yes, short summary", "bm": "Ya, ringkasan ringkas"},
                    {"key": "docs", "en": "View documents", "bm": "Lihat dokumen"},
                    {"key": "menu", "en": "Main menu", "bm": "Menu utama"},
                ],
            )
            return (
                f"Saya jumpa dokumen berkaitan.\n\n"
                f"Nama Dokumen: {best_row['document_name']}\n\n"
                f"Ringkasan:\n{summary}\n\n"
                f"{delivery_note}\n\n"
                f"{source_line_bm}"
                f"Adakah anda mahu ringkasan ringkas dokumen ini?"
            )

        delivery_note = (
            "I will send the document file here."
            if local_file
            else "The local file is not available yet, so please use the official link below."
        )

        set_ui_choices(
            "yesno_doc",
            [
                {"key": "yes", "en": "Yes, short summary", "bm": "Ya, ringkasan ringkas"},
                {"key": "docs", "en": "View documents", "bm": "Lihat dokumen"},
                {"key": "menu", "en": "Main menu", "bm": "Menu utama"},
            ],
        )
        return (
            f"I found a related document.\n\n"
            f"Document Name: {best_row['document_name']}\n\n"
            f"Summary:\n{summary}\n\n"
            f"{delivery_note}\n\n"
            f"{source_line_en}"
            f"Would you like a short summary of this document?"
        )

    return None


def search_official_web_source(user_input):
    cleaned = clean_text(user_input)
    award_keywords = {"anugerah", "award", "diraja", "canselor", "tokoh", "alumni", "psm", "ritec", "pingat", "dekan", "gpa", "cgpa"}
    if set(cleaned.split()) & award_keywords:
        return None
    """Return the most relevant catalogued official UTHM source when needed."""
    if web_sources_df.empty:
        return None

    cleaned_input = clean_text(user_input)
    input_tokens = set(cleaned_input.split())
    if len(input_tokens) < 2:
        return None

    # Align common Malay phrasing with bilingual labels on official UTHM pages.
    query_expansions = {
        "syarat": {"requirement", "requirements", "admission", "program", "programme"},
        "kemasukan": {"admission", "apply", "application", "program", "programme"},
        "jadual": {"schedule", "calendar", "timetable", "class", "lecture"},
        "waktu": {"schedule", "timetable", "class", "lecture"},
        "kuliah": {"lecture", "class", "schedule"},
        "graduasi": {"graduation", "convocation", "graduate"},
        "konvokesyen": {"convocation", "graduation", "graduate"},
        "transkrip": {"transcript", "certificate", "academic"},
        "sijil": {"certificate", "transcript", "academic"},
        "peperiksaan": {"exam", "examination", "schedule"},
        "yuran": {"tuition", "fee", "fees", "payment"},
    }
    expanded_tokens = set(input_tokens)
    for token in input_tokens:
        expanded_tokens.update(query_expansions.get(token, set()))

    best_row = None
    best_score = 0.0
    for _, row in web_sources_df.iterrows():
        searchable = " ".join(
            str(row.get(column, ""))
            # Page summaries contain shared navigation text, so they are not
            # suitable for ranking a precise request such as a transcript.
            for column in ("document_name", "keywords", "source_url")
        )
        source_tokens = set(clean_text(searchable).split())
        overlap = input_tokens & source_tokens
        expanded_overlap = expanded_tokens & source_tokens
        score = (len(overlap) * 1.25) + (len(expanded_overlap) * 0.45)
        if str(row.get("content_type", "")) == "web_page":
            score += 0.1
        if score > best_score:
            best_row = row
            best_score = score

    if best_row is None or best_score < 1.8:
        return None

    language = detect_language(user_input)
    document_name = str(best_row.get("document_name", "UTHM Academic Information"))
    source_url = str(best_row.get("source_url", "")).strip()
    if not source_url:
        return None

    conversation_context["last_intent"] = "official_web_source"
    conversation_context["last_document"] = document_name
    conversation_context["last_document_file"] = None
    conversation_context["last_language"] = language
    conversation_context["last_suggestions"] = []
    set_ui_choices("after", after_answer_choices(language))

    if language == "bm":
        return (
            f"Saya jumpa sumber rasmi UTHM yang berkaitan: {document_name}\n\n"
            f"Sila rujuk pautan ini untuk maklumat terkini:\n{source_url}"
        )

    return (
        f"I found a relevant official UTHM source: {document_name}\n\n"
        f"Please use this link for the latest information:\n{source_url}"
    )

def get_document_detail(document_name, language="en"):
    if str(document_name).startswith("Tuition Fee Structure "):
        faculty_code = str(document_name).replace("Tuition Fee Structure ", "").strip()
        rows = tuition_df[
            tuition_df["faculty_code"].astype(str).str.casefold() == faculty_code.casefold()
        ] if not tuition_df.empty else pd.DataFrame()

        if not rows.empty:
            fee_lines = [
                f"- {row['program_code']}: {format_fee_amount(row['total_tuition_fee_rm'])}"
                for _, row in rows.sort_values("program_code").iterrows()
            ]

            if language == "bm":
                return (
                    f"Dokumen ini menyenaraikan yuran pengajian antarabangsa untuk {faculty_code}. "
                    f"Ringkasan jumlah yuran program:\n" + "\n".join(fee_lines)
                )

            return (
                f"This document lists international tuition fees for {faculty_code}. "
                f"Programme fee summary:\n" + "\n".join(fee_lines)
            )

    details_en = {
        "Academic Calendar": (
            "The 2026/2027 Academic Calendar includes important dates such as semester dates, "
            "lecture weeks, holidays, revision week and examination weeks. "
            "Semester I runs from 21 September 2026 to 31 January 2027."
        ),
        "Academic Calendar 2025/2026 (English)": (
            "The archived 2025/2026 Academic Calendar includes semester dates, "
            "lecture weeks, holidays, revision week and examination weeks."
        ),
        "Academic Calendar 2025/2026 (BM)": (
            "The archived 2025/2026 Academic Calendar (Malay version) includes semester dates, "
            "lecture weeks, holidays, revision week and examination weeks."
        ),
        "Takwim Mesyuarat Senat 2026": (
            "This Senate meeting calendar lists 2026 Senate meeting dates and paper submission deadlines."
        ),
        "Takwim Mesyuarat JPA 2026": (
            "This JPA meeting calendar lists 2026 Academic Studies Committee meeting dates and paper submission deadlines."
        ),
        "Jadual Kerja Pelajar Semester I 2026/2027": (
            "This is the official student work schedule for Semester I of academic session 2026/2027."
        ),
        "Jadual Kerja Pelajar Semester Khas 2026/2027": (
            "This is the official student work schedule for the Special Semester of academic session 2026/2027."
        ),
        "Manual Pendaftaran Kursus SMAP AUTOREG": (
            "This SMAP AUTOREG manual explains how students register courses in the official student system."
        ),
        "Academic Regulation": (
            "The Academic Regulation document includes course registration rules, add/drop procedures, "
            "GPA and CGPA information, academic status, examination rules, and graduation requirements."
        ),
        "Final Examination Information": (
            "The Final Examination Information page provides details about examination schedules, "
            "final examination procedures, and official examination announcements."
        ),
        "Graduation Information": (
            "The Graduation Information page provides details about convocation, graduation status, "
            "eligibility, and related announcements."
        ),
        "Tuition Fee Information": (
            "The Tuition Fee Information page provides details about tuition fees, payment methods, "
            "and financial information for students."
        ),
        "PPA Contact Directory": (
            "The PPA Contact Directory provides official contact details such as phone numbers, "
            "emails, and office information."
        )
    }

    details_bm = {
        "Academic Calendar": (
            "Kalendar Akademik 2026/2027 mengandungi tarikh penting seperti tarikh semester, "
            "minggu kuliah, cuti, minggu ulang kaji dan minggu peperiksaan. "
            "Semester I berlangsung 21 September 2026 hingga 31 Januari 2027."
        ),
        "Academic Calendar 2025/2026 (English)": (
            "Kalendar Akademik arkib 2025/2026 mengandungi tarikh semester, "
            "minggu kuliah, cuti, minggu ulang kaji dan minggu peperiksaan."
        ),
        "Academic Calendar 2025/2026 (BM)": (
            "Kalendar Akademik arkib 2025/2026 (versi Bahasa Melayu) mengandungi tarikh semester, "
            "minggu kuliah, cuti, minggu ulang kaji dan minggu peperiksaan."
        ),
        "Takwim Mesyuarat Senat 2026": (
            "Takwim ini menyenaraikan tarikh mesyuarat Senat 2026 dan tarikh akhir penghantaran kertas kerja."
        ),
        "Takwim Mesyuarat JPA 2026": (
            "Takwim ini menyenaraikan tarikh mesyuarat JPA 2026 dan tarikh akhir penghantaran kertas kerja."
        ),
        "Jadual Kerja Pelajar Semester I 2026/2027": (
            "Ini ialah jadual kerja rasmi pelajar bagi Semester I sesi akademik 2026/2027."
        ),
        "Jadual Kerja Pelajar Semester Khas 2026/2027": (
            "Ini ialah jadual kerja rasmi pelajar bagi Semester Khas sesi akademik 2026/2027."
        ),
        "Manual Pendaftaran Kursus SMAP AUTOREG": (
            "Manual SMAP AUTOREG menerangkan cara pelajar mendaftar kursus dalam sistem rasmi."
        ),
        "Academic Regulation": (
            "The Academic Regulation document includes course registration rules, add/drop procedures, "
            "GPA and CGPA information, academic status, examination rules, and graduation requirements."
        ),
        "Final Examination Information": (
            "The Final Examination Information page provides details about examination schedules, "
            "final examination procedures, and official examination announcements."
        ),
        "Graduation Information": (
            "The Graduation Information page provides details about convocation, graduation status, "
            "eligibility, and related announcements."
        ),
        "Tuition Fee Information": (
            "The Tuition Fee Information page provides details about tuition fees, payment methods, "
            "and financial information for students."
        ),
        "PPA Contact Directory": (
            "The PPA Contact Directory provides official contact details such as phone numbers, "
            "emails, and office information."
        )
    }

    if language == "bm":
        return details_bm.get(document_name, "Tiada ringkasan tambahan untuk dokumen ini.")

    return details_en.get(document_name, "No additional summary is available for this document.")

def get_bot_response(user_input):
    cleaned_input = clean_text(user_input)
    lower_input = user_input.lower()

    last_prediction["intent"] = None
    last_prediction["confidence"] = 0
    conversation_context["last_document_file"] = None

    is_choice = cleaned_input.isdigit() or cleaned_input in yes_words
    if not is_choice:
        conversation_context["ui_kind"] = None
        conversation_context["ui_choices"] = []

    if (
        cleaned_input.isdigit()
        and conversation_context.get("last_intent") == "suggestion_request"
        and conversation_context.get("last_suggestions")
    ):
        selected_index = int(cleaned_input) - 1
        suggestions = conversation_context.get("last_suggestions", [])

        if 0 <= selected_index < len(suggestions):
            selected_row = pd.Series(suggestions[selected_index])
            conversation_context["last_suggestions"] = []
            last_prediction["intent"] = selected_row.get("intent")
            last_prediction["confidence"] = 1.0
            return build_response_from_row(selected_row, user_input)

        language = conversation_context.get("last_language", detect_language(user_input))
        suggestions = conversation_context.get("last_suggestions", [])
        set_ui_choices(
            "suggestion",
            [{"key": str(index), "en": row["question"], "bm": row["question"]} for index, row in enumerate(suggestions, start=1)],
        )
        if language == "bm":
            return "Sila pilih nombor cadangan yang sah, atau taip semula soalan anda."

        return "Please choose a valid suggestion number, or rephrase your question."

    if conversation_context.get("last_intent") == "suggestion_request":
        conversation_context["last_suggestions"] = []
        conversation_context["last_intent"] = None

    # 1. Greeting
    if cleaned_input in ["hi", "hello", "hai", "hey", "assalamualaikum"]:
        language = "bm" if cleaned_input in ["hai", "assalamualaikum"] else detect_language(user_input)
        if language == "bm":
            return (
                "Hai! Saya chatbot sokongan akademik.\n\n"
                "Anda boleh bertanya tentang GPA, CGPA, pendaftaran kursus, peperiksaan, "
                "graduasi, peraturan akademik, bayaran yuran, atau hubungan PPA."
            )

        return (
            "Hello! I am an academic chatbot.\n\n"
            "You can ask me about GPA, CGPA, course registration, examination, "
            "graduation, academic regulation, fee payment, or PPA contact."
        )

    # 2. Thank you
    if cleaned_input in ["thank you", "thanks", "terima kasih", "tq"]:
        language = detect_language(user_input)
        if language == "bm":
            return "Sama-sama! Adakah anda mahu bertanya soalan akademik yang lain?"

        return "You're welcome! Do you want to ask another academic question?"

    # 3. Help / Menu
    if cleaned_input in ["help", "menu", "bantuan"]:
        language = detect_language(user_input)
        if language == "bm":
            return (
                "Anda boleh bertanya tentang:\n\n"
                "- GPA dan CGPA\n"
                "- Pendaftaran kursus\n"
                "- Tambah/gugur kursus\n"
                "- Peperiksaan akhir\n"
                "- Graduasi\n"
                "- Peraturan akademik\n"
                "- Bayaran yuran\n"
                "- Hubungan PPA"
            )

        return (
            "You can ask me about:\n\n"
            "- GPA and CGPA\n"
            "- Course registration\n"
            "- Add/drop course\n"
            "- Final examination\n"
            "- Graduation\n"
            "- Academic regulation\n"
            "- Fee payment\n"
            "- PPA contact"
        )

    document_response = search_document(user_input)
    if document_response:
        conversation_context["last_intent"] = "document_request"
        last_prediction["intent"] = "document_request"
        last_prediction["confidence"] = 1.0
        return document_response

    if is_unsupported_subsidy_fee_query(cleaned_input):
        return build_missing_official_source_response(user_input)

    tuition_response = search_tuition_fee(user_input)
    if tuition_response:
        return tuition_response

    # 4. Study duration
    if any(word in cleaned_input for word in [
        "berapa lama pengajian",
        "tempoh pengajian",
        "berapa tahun belajar",
        "berapa semester"
    ]):
        matched_row, match_score = find_dataset_match(cleaned_input)
        if matched_row is not None and matched_row["intent"] == "study_duration":
            last_prediction["intent"] = matched_row["intent"]
            last_prediction["confidence"] = match_score
            return build_response_from_row(matched_row, user_input)

    # --- Direct Core Keyword Intent Shortcuts ---
    if any(term in cleaned_input for term in ["first class", "kelas pertama"]):
        last_prediction["intent"] = "degree_classification"
        last_prediction["confidence"] = 1.0
        return build_response("degree_classification", user_input)

    if any(term in cleaned_input for term in ["etika pemakaian", "pakaian", "dress code"]):
        last_prediction["intent"] = "etika_pemakaian"
        last_prediction["confidence"] = 1.0
        return build_response("etika_pemakaian", user_input)

    if any(term in cleaned_input for term in ["dekan", "dean"]):
        last_prediction["intent"] = "deans_award"
        last_prediction["confidence"] = 1.0
        return build_response("deans_award", user_input)

    if any(term in cleaned_input for term in ["diraja", "royal"]):
        last_prediction["intent"] = "anugerah_diraja"
        last_prediction["confidence"] = 1.0
        return build_response("anugerah_diraja", user_input)

    if any(term in cleaned_input for term in ["canselor", "chancellor"]):
        last_prediction["intent"] = "anugerah_canselor"
        last_prediction["confidence"] = 1.0
        return build_response("anugerah_canselor", user_input)

    if any(term in cleaned_input for term in ["muet"]):
        last_prediction["intent"] = "ppa_muet_info"
        last_prediction["confidence"] = 1.0
        return build_response("ppa_muet_info", user_input)

    if any(term in cleaned_input for term in ["rayuan gred", "semak gred", "rayuan gred subjek", "appeal grade"]):
        last_prediction["intent"] = "special_exam_appeal"
        last_prediction["confidence"] = 1.0
        return build_response("special_exam_appeal", user_input)

    if any(term in cleaned_input for term in ["surat pengesahan", "verification letter"]):
        last_prediction["intent"] = "ppa_student_verification_letter"
        last_prediction["confidence"] = 1.0
        return build_response("ppa_student_verification_letter", user_input)

    if any(term in cleaned_input for term in ["ptptn"]):
        last_prediction["intent"] = "ppa_ptptn_exemption"
        last_prediction["confidence"] = 1.0
        return build_response("ppa_ptptn_exemption", user_input)

    if any(term in cleaned_input for term in ["hubungi ppa", "contact ppa", "nombor ppa", "pejabat ppa", "telefon ppa"]):
        last_prediction["intent"] = "contact_ppa"
        last_prediction["confidence"] = 1.0
        return build_response("contact_ppa", user_input)

    # --- STAGE 1: Dataset Exact / High Similarity Match ---
    matched_row, match_score = find_dataset_match(cleaned_input)

    if matched_row is not None:
        last_prediction["intent"] = matched_row["intent"]
        last_prediction["confidence"] = match_score
        return build_response_from_row(matched_row, user_input)

    # --- STAGE 2: Gemini Generative AI RAG Engine ---
    gemini_answer = query_gemini(user_input, conversation_context)
    if gemini_answer:
        last_prediction["intent"] = "gemini_llm_rag"
        last_prediction["confidence"] = 0.99
        conversation_context["last_intent"] = "gemini_llm_rag"
        language = detect_language(user_input)
        conversation_context["last_language"] = language
        set_ui_choices("after", after_answer_choices(language))
        return gemini_answer

    # --- STAGE 2: Vector RAG Semantic Engine Search ---
    try:
        semantic_results = semantic_engine.search(cleaned_input, top_k=1, min_similarity=0.28)
        if semantic_results:
            best_semantic = semantic_results[0]
            matched_intent = best_semantic.get("intent")
            if matched_intent:
                intent_rows = df[df["intent"] == matched_intent]
                if not intent_rows.empty:
                    last_prediction["intent"] = matched_intent
                    last_prediction["confidence"] = best_semantic.get("similarity_score", 0.70)
                    return build_response_from_row(intent_rows.iloc[0], user_input)
    except Exception:
        pass

    # 6. Shortcut rules
    if cleaned_input in ["daftar kursus", "daftar subjek", "pendaftaran kursus", "register course", "course registration"]:
        last_prediction["intent"] = "course_registration"
        last_prediction["confidence"] = 1.0
        return build_response("course_registration", user_input)

    if cleaned_input in ["gugur subjek", "gugur kursus", "tambah kursus", "tambah subjek", "add course", "drop course"]:
        last_prediction["intent"] = "add_drop_course"
        last_prediction["confidence"] = 1.0
        return build_response("add_drop_course", user_input)

    if cleaned_input in ["peperiksaan akhir", "jadual peperiksaan", "exam timetable", "final exam", "final examination"]:
        last_prediction["intent"] = "final_exam"
        last_prediction["confidence"] = 1.0
        return build_response("final_exam", user_input)

    if cleaned_input in ["graduation", "graduate", "convocation", "konvokesyen"]:
        last_prediction["intent"] = "graduation"
        last_prediction["confidence"] = 1.0
        return build_response("graduation", user_input)

    if cleaned_input in ["academic regulation", "peraturan akademik", "academic rules"]:
        last_prediction["intent"] = "academic_regulation"
        last_prediction["confidence"] = 1.0
        return build_response("academic_regulation", user_input)

    if cleaned_input in ["yuran", "bayar yuran", "fee payment", "tuition fee"]:
        last_prediction["intent"] = "fee_payment"
        last_prediction["confidence"] = 1.0
        return build_response("fee_payment", user_input)

    if any(phrase in cleaned_input for phrase in [
        "yuran pengajian",
        "berapa yuran",
        "semak yuran",
        "tuition fee",
        "fee amount",
        "study fee"
    ]):
        last_prediction["intent"] = "fee_payment"
        last_prediction["confidence"] = 1.0
        return build_response("fee_payment", user_input)

    if cleaned_input in ["ppa contact", "contact ppa", "hubungi ppa", "ppa"]:
        last_prediction["intent"] = "contact_ppa"
        last_prediction["confidence"] = 1.0
        return build_response("contact_ppa", user_input)

    ppa_title_shortcuts = {
        "ppa_class_schedule": [
            "jadual waktu kuliah akademik",
            "jadual kuliah akademik",
            "academic class schedule",
            "class schedule"
        ],
        "ppa_student_work_schedule": [
            "jadual kerja pelajar",
            "student work schedule"
        ],
        "ppa_muet_info": [
            "kalendar muet",
            "muet calendar",
            "muet information",
            "maklumat muet"
        ],
        "ppa_graduate_list": [
            "senarai graduan uthm",
            "graduate list",
            "list of uthm graduates"
        ],
        "ppa_ptptn_exemption": [
            "pengecualian ptptn",
            "ptptn exemption"
        ],
        "ppa_shared_lecture_room": [
            "ruang kuliah gunasama",
            "ruang guna sama",
            "shared lecture room"
        ],
        "ppa_online_applications": [
            "aplikasi online",
            "aplikasi atas talian",
            "online applications"
        ]
    }

    for intent, phrases in ppa_title_shortcuts.items():
        if cleaned_input in phrases:
            last_prediction["intent"] = intent
            last_prediction["confidence"] = 1.0
            return build_response(intent, user_input)

    # 7. Context follow-up
    last_intent = conversation_context.get("last_intent")

    if cleaned_input in yes_words and last_intent == "document_request":
        last_document = conversation_context.get("last_document")
        language = conversation_context.get("last_language", detect_language(user_input))

        conversation_context["last_intent"] = None
        conversation_context["last_document"] = None
        conversation_context["last_document_file"] = None

        if language == "bm":
            display_name = get_document_display_name(last_document, language)
            return (
                f"Ini ringkasan ringkas untuk {display_name}:\n\n"
                f"{get_document_detail(last_document, language)}\n\n"
                "Anda boleh taip soalan akademik seterusnya."
            )

        return (
            f"Here is a short summary of {last_document}:\n\n"
            f"{get_document_detail(last_document, language)}\n\n"
            "Please type your next academic question."
        )

    if cleaned_input in yes_words or cleaned_input.isdigit() or is_academic_like(cleaned_input):
        context_response = handle_context_follow_up(cleaned_input, last_intent, user_input)
        if context_response:
            return context_response

    if cleaned_input in yes_words:
        language = conversation_context.get("last_language", detect_language(user_input))
        if language == "bm":
            return "Baik. Sila taip soalan akademik seterusnya."

        return "Sure. Please type your next academic question."

    # 9. AI model prediction
    try:
        predicted_intent = model.predict([cleaned_input])[0]
        confidence = max(model.predict_proba([cleaned_input])[0])

        print("DEBUG Intent:", predicted_intent)
        print("DEBUG Confidence:", round(confidence, 2))
        print("LAST INTENT:", last_intent)

        if confidence >= MODEL_CONFIDENCE_THRESHOLD:
            last_prediction["intent"] = predicted_intent
            last_prediction["confidence"] = confidence
            return build_response(predicted_intent, user_input)
    except Exception:
        pass

    # 10. Official Web Source Fallback (Only if Dataset, Vector Search, and ML Model fail)
    official_source_response = search_official_web_source(user_input)
    if official_source_response:
        last_prediction["intent"] = "official_web_source"
        last_prediction["confidence"] = 1.0
        return official_source_response

    last_prediction["intent"] = None
    last_prediction["confidence"] = confidence

    suggestions = find_dataset_suggestions(cleaned_input)
    if suggestions and (is_academic_like(cleaned_input) or max(score_dataset_question(cleaned_input, row["clean_question"]) for row in suggestions) >= 0.70):
        return build_suggestion_response(suggestions, user_input)

    # 10. Fallback
    language = detect_language(user_input)
    set_ui_choices("after", after_answer_choices(language))
    if language == "bm":
        return (
            "Maaf, saya tidak mempunyai maklumat yang cukup untuk menjawab soalan itu.\n\n"
            "Anda boleh bertanya tentang:\n"
            "- GPA dan CGPA\n"
            "- Pendaftaran kursus\n"
            "- Tambah/gugur kursus\n"
            "- Peperiksaan akhir\n"
            "- Graduasi\n"
            "- Peraturan akademik\n"
            "- Bayaran yuran\n"
            "- Hubungan PPA\n"
            "- Borang dan dokumen akademik\n\n"
            "Untuk soalan di luar maklumat akademik, sila hubungi pejabat berkaitan."
        )

    return (
        "Sorry, I do not have enough information to answer that question.\n\n"
        "You may ask me about:\n"
        "- GPA and CGPA\n"
        "- Course registration\n"
        "- Add/drop course\n"
        "- Final examination\n"
        "- Graduation\n"
        "- Academic regulation\n"
        "- Fee payment\n"
        "- PPA contact\n"
        "- Academic forms and documents\n\n"
        "For questions outside academic information, please contact the related office."
    )
