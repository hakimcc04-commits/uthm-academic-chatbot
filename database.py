import hashlib
import re
from datetime import datetime
from difflib import SequenceMatcher

from db import connect_db


def create_tables():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Admin (
        admin_id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(100) NOT NULL UNIQUE,
        password VARCHAR(255) NOT NULL,
        email VARCHAR(255),
        mfa_secret VARCHAR(128) NULL,
        mfa_enabled TINYINT(1) NOT NULL DEFAULT 0,
        email_mfa_enabled TINYINT(1) NOT NULL DEFAULT 0,
        email_otp VARCHAR(128) NULL,
        email_otp_expires VARCHAR(50) NULL,
        backup_codes TEXT NULL,
        failed_attempts INT NOT NULL DEFAULT 0,
        locked_until VARCHAR(50) NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Student (
        student_id INT AUTO_INCREMENT PRIMARY KEY,
        telegram_id VARCHAR(100) UNIQUE,
        student_name VARCHAR(255),
        email VARCHAR(255),
        created_date VARCHAR(50)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS FAQ (
        faq_id INT AUTO_INCREMENT PRIMARY KEY,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        keyword TEXT NOT NULL,
        category VARCHAR(100),
        admin_id INT,
        created_date VARCHAR(50),
        updated_date VARCHAR(50),
        FOREIGN KEY (admin_id) REFERENCES Admin(admin_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS User_Query (
        query_id INT AUTO_INCREMENT PRIMARY KEY,
        student_id INT,
        user_question TEXT NOT NULL,
        intent VARCHAR(100),
        query_date VARCHAR(50),
        status VARCHAR(50),
        FOREIGN KEY (student_id) REFERENCES Student(student_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Chatbot_Response (
        response_id INT AUTO_INCREMENT PRIMARY KEY,
        query_id INT,
        response_text TEXT NOT NULL,
        response_date VARCHAR(50),
        feedback VARCHAR(50),
        FOREIGN KEY (query_id) REFERENCES User_Query(query_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Reports (
        report_id INT AUTO_INCREMENT PRIMARY KEY,
        admin_id INT,
        total_queries INT,
        total_unanswered INT,
        most_asked_category VARCHAR(100),
        generated_date VARCHAR(50),
        FOREIGN KEY (admin_id) REFERENCES Admin(admin_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def insert_default_admin():
    conn = connect_db()
    cursor = conn.cursor()

    hashed_password = hash_password("admin123")

    cursor.execute("""
    INSERT IGNORE INTO Admin (username, password, email)
    VALUES (%s, %s, %s)
    """, ("admin", hashed_password, "admin@uthm.edu.my"))

    conn.commit()
    conn.close()


def insert_sample_faq():
    conn = connect_db()
    cursor = conn.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    faq_data = [
        (
            "How can I register for courses?",
            "Students can register for courses through the official university student portal during the course registration period.",
            "course registration register subject add drop",
            "Course Registration",
            1,
            now,
            now
        ),
        (
            "Where can I check the examination timetable?",
            "Students can check the examination timetable through the official university academic portal or announcement platform.",
            "exam examination timetable schedule final test",
            "Examination",
            1,
            now,
            now
        ),
        (
            "How can I check academic regulations?",
            "Academic regulations can be referred to through the university academic handbook or official academic management office documents.",
            "academic regulation rules handbook guideline",
            "Academic Regulation",
            1,
            now,
            now
        ),
        (
            "Who should I contact for academic enquiries?",
            "For further academic enquiries, students may contact the Pejabat Pengurusan Akademik (PPA) or the relevant faculty academic office.",
            "contact ppa academic office enquiry help",
            "General Enquiry",
            1,
            now,
            now
        ),
        (
            "How can I apply for graduation?",
            "Graduation application procedures are usually announced by the university. Students should refer to the official academic portal for updated information.",
            "graduation apply convocation graduate",
            "Graduation",
            1,
            now,
            now
        )
    ]

    cursor.executemany("""
    INSERT INTO FAQ (question, answer, keyword, category, admin_id, created_date, updated_date)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, faq_data)

    conn.commit()
    conn.close()


def get_or_create_student(telegram_id, student_name=None):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("SELECT student_id FROM Student WHERE telegram_id = %s", (telegram_id,))
    student = cursor.fetchone()

    if student:
        conn.close()
        return student[0]

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
    INSERT INTO Student (telegram_id, student_name, email, created_date)
    VALUES (%s, %s, %s, %s)
    """, (telegram_id, student_name, None, now))

    conn.commit()
    student_id = cursor.lastrowid
    conn.close()

    return student_id


def search_faq(user_input):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT faq_id, question, answer, keyword, category
        FROM FAQ
    """)

    faqs = cursor.fetchall()
    conn.close()

    # Synonym dictionary to improve matching accuracy
    synonyms = {
        "hostel": ["hostel", "accommodation", "college", "residential", "dormitory", "kolej", "kediaman"],
        "exam": ["exam", "examination", "test", "final", "paper", "timetable", "schedule"],
        "course": ["course", "subject", "registration", "register", "add", "drop", "enroll"],
        "graduation": ["graduation", "graduate", "convocation", "apply"],
        "academic": ["academic", "regulation", "rules", "handbook", "guideline", "policy"],
        "contact": ["contact", "office", "ppa", "help", "enquiry", "support"]
    }

    def clean_text(text):
        text = str(text).lower()
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def expand_words(words):
        expanded = set(words)

        for word in words:
            for key, synonym_list in synonyms.items():
                if word in synonym_list:
                    expanded.update(synonym_list)

        return expanded

    cleaned_input = clean_text(user_input)
    user_words = set(cleaned_input.split())
    expanded_user_words = expand_words(user_words)

    best_match = None
    highest_score = 0
    best_confidence = 0

    for faq in faqs:
        faq_id, question, answer, keyword, category = faq

        cleaned_question = clean_text(question)
        cleaned_keyword = clean_text(keyword)
        question_words = set(cleaned_question.split())
        keyword_words = set(cleaned_keyword.split())
        searchable_words = question_words | keyword_words
        expanded_keyword_words = expand_words(searchable_words)

        original_matched_words = user_words.intersection(searchable_words)
        matched_words = expanded_user_words.intersection(expanded_keyword_words)

        overlap_score = len(matched_words) / max(len(expanded_user_words), 1)
        question_similarity = SequenceMatcher(None, cleaned_input, cleaned_question).ratio()
        keyword_similarity = SequenceMatcher(None, cleaned_input, cleaned_keyword).ratio() if cleaned_keyword else 0
        exact_bonus = 0.25 if cleaned_input and cleaned_input in cleaned_question else 0
        score = max(overlap_score, question_similarity, keyword_similarity) + exact_bonus

        has_reliable_match = (
            overlap_score >= 0.35
            or question_similarity >= 0.82
            or keyword_similarity >= 0.82
        )
        strong_single_words = {
            "academic", "akademik", "course", "courses", "subject", "subjects",
            "subjek", "exam", "examination", "peperiksaan", "fee", "fees",
            "yuran", "cgpa", "gpa", "ppa", "smap", "graduation", "graduasi",
            "convocation", "konvokesyen", "document", "dokumen"
        }
        has_reliable_word = (
            len(original_matched_words) >= 2
            or bool(original_matched_words & strong_single_words)
            or question_similarity >= 0.82
            or keyword_similarity >= 0.82
        )

        if not has_reliable_match or not has_reliable_word:
            continue

        confidence = round(min(score, 1) * 100, 2)

        if score > highest_score:
            highest_score = score
            best_confidence = confidence

            best_match = {
                "faq_id": faq_id,
                "question": question,
                "answer": answer,
                "keyword": keyword,
                "category": category,
                "score": round(score, 3),
                "confidence": best_confidence
            }

    # Minimum threshold to avoid wrong answer
    if best_match and highest_score >= 0.52:
        return best_match

    return None


def save_query(student_id, user_question, intent=None, status="answered"):
    conn = connect_db()
    cursor = conn.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
    INSERT INTO User_Query (student_id, user_question, intent, query_date, status)
    VALUES (%s, %s, %s, %s, %s)
    """, (student_id, user_question, intent, now, status))

    conn.commit()
    query_id = cursor.lastrowid
    conn.close()

    return query_id


def save_response(query_id, response_text):
    conn = connect_db()
    cursor = conn.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
    INSERT INTO Chatbot_Response (query_id, response_text, response_date, feedback)
    VALUES (%s, %s, %s, %s)
    """, (query_id, response_text, now, None))

    conn.commit()
    conn.close()


def view_all_faq():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("SELECT faq_id, question, answer, category FROM FAQ")
    faqs = cursor.fetchall()

    conn.close()
    return faqs

def save_feedback(student_id, feedback_text):
    conn = connect_db()
    cursor = conn.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
    INSERT INTO User_Query (student_id, user_question, intent, query_date, status)
    VALUES (%s, %s, %s, %s, %s)
    """, (student_id, "Feedback", "Feedback", now, "feedback"))

    query_id = cursor.lastrowid

    cursor.execute("""
    INSERT INTO Chatbot_Response (query_id, response_text, response_date, feedback)
    VALUES (%s, %s, %s, %s)
    """, (query_id, "User feedback recorded", now, feedback_text))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    create_tables()
    insert_default_admin()
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM FAQ")
    faq_count = cursor.fetchone()[0]
    conn.close()
    if faq_count == 0:
        insert_sample_faq()
        print("Sample FAQ inserted.")
    else:
        print("Existing FAQ records kept.")
    print("MySQL database ready.")
    print("Default admin created if it did not already exist.")
