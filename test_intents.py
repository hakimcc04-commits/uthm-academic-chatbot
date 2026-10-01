from nlp import get_bot_response, last_prediction

test_cases = [
    ("How do I register courses?", "course_registration"),
    ("Macam mana nak daftar kursus?", "course_registration"),
    ("How can I drop a subject?", "add_drop_course"),
    ("Macam mana nak gugur subjek?", "add_drop_course"),
    ("When is the final examination?", "final_exam"),
    ("Bila peperiksaan akhir?", "final_exam"),
    ("Where can I find the academic calendar?", "academic_calendar"),
    ("Di mana kalendar akademik?", "academic_calendar"),
    ("What is GPA?", "cgpa_gpa"),
    ("Apa itu CGPA?", "cgpa_gpa"),
    ("How do I apply for graduation?", "graduation"),
    ("Macam mana nak mohon graduasi?", "graduation"),
    ("How can I pay tuition fees?", "fee_payment"),
    ("Macam mana nak bayar yuran?", "fee_payment"),
    ("How do I contact PPA?", "contact_ppa"),
    ("Macam mana nak hubungi PPA?", "contact_ppa"),
    ("I need academic regulation document", "document_request"),
    ("Saya nak dokumen peraturan akademik", "document_request"),
]

correct = 0

print("No,Input,Expected Intent,Actual Intent,Confidence,Result")

for i, (question, expected) in enumerate(test_cases, start=1):
    response = get_bot_response(question)

    actual = last_prediction["intent"]
    confidence = last_prediction["confidence"]

    result = "Pass" if actual == expected else "Fail"

    if result == "Pass":
        correct += 1

    print(f'{i},"{question}",{expected},{actual},{confidence:.2f},{result}')

print("\nTotal Correct:", correct)
print("Total Test:", len(test_cases))
print("Accuracy:", round((correct / len(test_cases)) * 100, 2), "%")