import hashlib
from datetime import datetime
from getpass import getpass

from db import connect_db


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def admin_login():
    print("\n=== Admin Login ===")
    username = input("Username: ").strip()
    password = hash_password(getpass("Password: "))

    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT admin_id FROM Admin
        WHERE username = %s AND password = %s
    """, (username, password))

    admin = cursor.fetchone()
    conn.close()

    if admin:
        print("\nLogin successful.")
        return admin[0]

    print("\nInvalid username or password.")
    return None


def view_faq():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT faq_id, question, answer, keyword, category
        FROM FAQ
        ORDER BY faq_id
    """)

    faqs = cursor.fetchall()
    conn.close()

    print("\n=== FAQ List ===")

    if not faqs:
        print("No FAQ records found.")
        return

    for faq in faqs:
        print(f"\nFAQ ID   : {faq[0]}")
        print(f"Question : {faq[1]}")
        print(f"Answer   : {faq[2]}")
        print(f"Keyword  : {faq[3]}")
        print(f"Category : {faq[4]}")


def add_faq(admin_id):
    print("\n=== Add FAQ ===")

    question = input("Question: ").strip()
    answer = input("Answer: ").strip()
    keyword = input("Keywords: ").strip()
    category = input("Category: ").strip()

    if not question or not answer or not keyword:
        print("Question, answer, and keyword cannot be empty.")
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO FAQ
        (question, answer, keyword, category, admin_id, created_date, updated_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (question, answer, keyword, category, admin_id, now, now))

    conn.commit()
    conn.close()

    print("FAQ added successfully.")


def update_faq(admin_id):
    print("\n=== Update FAQ ===")
    view_faq()

    faq_id = input("\nEnter FAQ ID to update: ").strip()

    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM FAQ WHERE faq_id = %s", (faq_id,))
    faq = cursor.fetchone()

    if not faq:
        print("FAQ not found.")
        conn.close()
        return

    print("\nLeave blank if you do not want to change the value.")

    new_question = input("New Question: ").strip()
    new_answer = input("New Answer: ").strip()
    new_keyword = input("New Keywords: ").strip()
    new_category = input("New Category: ").strip()

    question = new_question if new_question else faq[1]
    answer = new_answer if new_answer else faq[2]
    keyword = new_keyword if new_keyword else faq[3]
    category = new_category if new_category else faq[4]

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        UPDATE FAQ
        SET question = %s, answer = %s, keyword = %s, category = %s, admin_id = %s, updated_date = %s
        WHERE faq_id = %s
    """, (question, answer, keyword, category, admin_id, now, faq_id))

    conn.commit()
    conn.close()

    print("FAQ updated successfully.")


def delete_faq():
    print("\n=== Delete FAQ ===")
    view_faq()

    faq_id = input("\nEnter FAQ ID to delete: ").strip()

    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM FAQ WHERE faq_id = %s", (faq_id,))
    faq = cursor.fetchone()

    if not faq:
        print("FAQ not found.")
        conn.close()
        return

    confirm = input("Are you sure you want to delete this FAQ? (yes/no): ").lower().strip()

    if confirm == "yes":
        cursor.execute("DELETE FROM FAQ WHERE faq_id = %s", (faq_id,))
        conn.commit()
        print("FAQ deleted successfully.")
    else:
        print("Delete cancelled.")

    conn.close()


def view_unanswered_queries():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT query_id, user_question, intent, query_date
        FROM User_Query
        WHERE status = 'unanswered'
        ORDER BY query_date DESC
    """)

    queries = cursor.fetchall()
    conn.close()

    print("\n=== Unanswered Queries ===")

    if not queries:
        print("No unanswered queries found.")
        return

    for query in queries:
        print(f"\nQuery ID : {query[0]}")
        print(f"Question : {query[1]}")
        print(f"Intent   : {query[2]}")
        print(f"Date     : {query[3]}")


def add_faq_from_unanswered(admin_id):
    print("\n=== Add FAQ From Unanswered Query ===")
    view_unanswered_queries()

    query_id = input("\nEnter Query ID to convert into FAQ: ").strip()

    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT user_question, intent
        FROM User_Query
        WHERE query_id = %s AND status = 'unanswered'
    """, (query_id,))

    query = cursor.fetchone()

    if not query:
        print("Unanswered query not found.")
        conn.close()
        return

    question = query[0]
    category = query[1] if query[1] else "General"

    print(f"\nQuestion: {question}")
    answer = input("Enter answer for this FAQ: ").strip()
    keyword = input("Enter keywords: ").strip()

    if not answer or not keyword:
        print("Answer and keywords cannot be empty.")
        conn.close()
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO FAQ
        (question, answer, keyword, category, admin_id, created_date, updated_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (question, answer, keyword, category, admin_id, now, now))

    cursor.execute("""
        UPDATE User_Query
        SET status = 'converted_to_faq'
        WHERE query_id = %s
    """, (query_id,))

    conn.commit()
    conn.close()

    print("Unanswered query converted into FAQ successfully.")


def view_query_history():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT query_id, user_question, intent, status, query_date
        FROM User_Query
        ORDER BY query_date DESC
        LIMIT 20
    """)

    queries = cursor.fetchall()
    conn.close()

    print("\n=== Latest Query History ===")

    if not queries:
        print("No query history found.")
        return

    for query in queries:
        print(f"\nQuery ID : {query[0]}")
        print(f"Question : {query[1]}")
        print(f"Intent   : {query[2]}")
        print(f"Status   : {query[3]}")
        print(f"Date     : {query[4]}")


def generate_report(admin_id, export=False):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM User_Query")
    total_queries = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM User_Query
        WHERE status IN ('answered', 'auto_approved', 'auto_approved_faq', 'needs_clarification')
    """)
    total_answered = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM User_Query WHERE status='unanswered'")
    total_unanswered = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM User_Query WHERE status='converted_to_faq'")
    converted_to_faq = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM FAQ")
    total_faq = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM Chatbot_Response WHERE feedback IS NOT NULL")
    total_feedback = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM Chatbot_Response WHERE feedback='Helpful'")
    helpful_feedback = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM Chatbot_Response WHERE feedback='Not Helpful'")
    not_helpful_feedback = cursor.fetchone()[0]

    cursor.execute("""
        SELECT intent, COUNT(*) AS total
        FROM User_Query
        WHERE intent IS NOT NULL
        GROUP BY intent
        ORDER BY total DESC
        LIMIT 1
    """)

    result = cursor.fetchone()
    most_asked_intent = result[0] if result else "None"

    generated_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO Reports
        (admin_id, total_queries, total_unanswered, most_asked_category, generated_date)
        VALUES (%s, %s, %s, %s, %s)
    """, (admin_id, total_queries, total_unanswered, most_asked_intent, generated_date))

    conn.commit()
    conn.close()

    report_text = f"""
==================================================
CHATBOT ANALYTICS REPORT
==================================================
Generated Date          : {generated_date}

Total Queries           : {total_queries}
Answered Queries        : {total_answered}
Unanswered Queries      : {total_unanswered}
Converted To FAQ        : {converted_to_faq}

Total FAQ Records       : {total_faq}

Total Feedback          : {total_feedback}
Helpful Feedback        : {helpful_feedback}
Not Helpful Feedback    : {not_helpful_feedback}

Most Asked Intent       : {most_asked_intent}
==================================================
"""

    print(report_text)

    if export:
        filename = f"chatbot_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        with open(filename, "w", encoding="utf-8") as file:
            file.write(report_text)

        print(f"Report exported successfully: {filename}")


def admin_menu(admin_id):
    while True:
        print("\n=== Admin Dashboard ===")
        print("1. View FAQ")
        print("2. Add FAQ")
        print("3. Update FAQ")
        print("4. Delete FAQ")
        print("5. View Unanswered Queries")
        print("6. Add FAQ From Unanswered Query")
        print("7. View Query History")
        print("8. Generate Report")
        print("9. Export Report to TXT")
        print("10. Logout")

        choice = input("Choose option: ").strip()

        if choice == "1":
            view_faq()
        elif choice == "2":
            add_faq(admin_id)
        elif choice == "3":
            update_faq(admin_id)
        elif choice == "4":
            delete_faq()
        elif choice == "5":
            view_unanswered_queries()
        elif choice == "6":
            add_faq_from_unanswered(admin_id)
        elif choice == "7":
            view_query_history()
        elif choice == "8":
            generate_report(admin_id, export=False)
        elif choice == "9":
            generate_report(admin_id, export=True)
        elif choice == "10":
            print("Logged out.")
            break
        else:
            print("Invalid option. Please try again.")


def main():
    admin_id = admin_login()

    if admin_id:
        admin_menu(admin_id)


if __name__ == "__main__":
    main()
