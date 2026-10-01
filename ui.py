from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

DOC_PAGE_SIZE = 8
FAQ_PAGE_SIZE = 8
NUMBERS_PER_ROW = 4

# Telegram renders the primary style with its theme-aware academic blue.  Keep
# it for only the main actions so option lists remain calm and easy to scan.
PRIMARY_BUTTON_STYLE = {"style": "primary"}


def primary_inline_button(text, callback_data):
    """Create an inline button with Telegram's theme-aware primary colour."""
    return InlineKeyboardButton(
        text,
        callback_data=callback_data,
        api_kwargs=PRIMARY_BUTTON_STYLE,
    )


def primary_reply_button(text):
    """Create a reply-keyboard button with Telegram's theme-aware primary colour."""
    return KeyboardButton(text, api_kwargs=PRIMARY_BUTTON_STYLE)

MAIN_REPLY = ReplyKeyboardMarkup(
    [
        [primary_reply_button("💬 Ask Question"), "📄 Documents"],
        ["💳 Tuition Fees", "❓ FAQ"],
        ["ℹ️ Help", "⭐ Feedback"],
        [primary_reply_button("🏠 Main Menu")],
    ],
    resize_keyboard=True,
    # A persistent keyboard cannot be minimized in Telegram. Keep the menu
    # available, but let students hide it whenever they need more chat space.
    is_persistent=False,
    input_field_placeholder="Type a question or tap a button...",
)

FEEDBACK_REPLY = ReplyKeyboardMarkup(
    [
        ["👍 Helpful", "👎 Not Helpful"],
        [primary_reply_button("🏠 Main Menu")],
    ],
    resize_keyboard=True,
)


def _chunk(items, size):
    return [items[index:index + size] for index in range(0, len(items), size)]


def home_keyboard():
    return InlineKeyboardMarkup(
        [
            [primary_inline_button("💬 Ask Question", "go:ask")],
            [
                InlineKeyboardButton("📄 Documents", callback_data="go:docs"),
                InlineKeyboardButton("💰 Tuition Fees", callback_data="go:fees"),
            ],
            [
                InlineKeyboardButton("📘 Academic Regulations", callback_data="go:regulations"),
                InlineKeyboardButton("🏆 Awards & Recognition", callback_data="go:awards"),
            ],
            [
                InlineKeyboardButton("📊 Visual Diagrams", callback_data="go:diagrams"),
                InlineKeyboardButton("📅 Calendar", callback_data="quick:calendar"),
            ],
            [
                InlineKeyboardButton("❓ FAQ", callback_data="go:faq"),
                InlineKeyboardButton("⭐ Feedback", callback_data="go:fb"),
                InlineKeyboardButton("ℹ️ Help", callback_data="go:help"),
            ],
        ]
    )


def nav_row(extra=None):
    row = extra[:] if extra else []
    row.append(primary_inline_button("🏠 Main Menu", "go:home"))
    return row


def numbered_rows(count, prefix, start_index=0, per_row=NUMBERS_PER_ROW):
    buttons = [
        InlineKeyboardButton(str(start_index + offset + 1), callback_data=f"{prefix}{start_index + offset}")
        for offset in range(count)
    ]
    return _chunk(buttons, per_row)


def document_category_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📅 Calendar & Schedule", callback_data="docs:cat:calendar")],
            [InlineKeyboardButton("📝 Academic Forms", callback_data="docs:cat:forms")],
            [InlineKeyboardButton("📘 Guides & Regulations", callback_data="docs:cat:guides")],
            [InlineKeyboardButton("💰 Tuition Fee PDFs", callback_data="docs:cat:fees")],
            [InlineKeyboardButton("📦 Archive 2025/2026", callback_data="docs:cat:archive")],
            [InlineKeyboardButton("📋 All Documents", callback_data="docs:cat:all")],
            nav_row(),
        ]
    )


def document_list_keyboard(page_items, page, total_pages, start_index):
    rows = numbered_rows(len(page_items), "docs:i:", start_index)
    pager = []
    if page > 0:
        pager.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"docs:p:{page - 1}"))
    if page < total_pages - 1:
        pager.append(InlineKeyboardButton("Next ➡️", callback_data=f"docs:p:{page + 1}"))
    if pager:
        rows.append(pager)
    rows.append(
        [
            InlineKeyboardButton("📂 Categories", callback_data="docs:cats"),
            primary_inline_button("🏠 Main Menu", "go:home"),
        ]
    )
    return InlineKeyboardMarkup(rows)


def after_document_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📄 Another Document", callback_data="go:docs")],
            [
                InlineKeyboardButton("💬 Ask Question", callback_data="go:ask"),
                primary_inline_button("🏠 Main Menu", "go:home"),
            ],
        ]
    )


def faculty_keyboard(faculty_codes):
    rows = _chunk(
        [InlineKeyboardButton(code, callback_data=f"fees:fac:{code}") for code in faculty_codes],
        3,
    )
    return InlineKeyboardMarkup(rows)


def tuition_level_keyboard():
    """Choose a study level before showing its official fee PDFs."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🎓 Diploma", callback_data="fees:level:diploma")],
            [InlineKeyboardButton("📘 Sarjana Muda", callback_data="fees:level:bachelor")],
            [InlineKeyboardButton("📚 Master", callback_data="fees:level:master")],
            [InlineKeyboardButton("🔬 PhD", callback_data="fees:level:phd")],
            nav_row(),
        ]
    )


def program_keyboard(programs, faculty_code):
    rows = numbered_rows(len(programs), f"fees:i:{faculty_code}:")
    rows.append([InlineKeyboardButton("📎 Faculty PDF", callback_data=f"fees:pdf:{faculty_code}")])
    rows.append(
        [
            InlineKeyboardButton("⬅️ Faculties", callback_data="go:fees"),
            primary_inline_button("🏠 Main Menu", "go:home"),
        ]
    )
    return InlineKeyboardMarkup(rows)


def faq_list_keyboard(page_items, page, total_pages, start_index):
    rows = numbered_rows(len(page_items), "faq:i:", start_index)
    pager = []
    if page > 0:
        pager.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"faq:p:{page - 1}"))
    if page < total_pages - 1:
        pager.append(InlineKeyboardButton("Next ➡️", callback_data=f"faq:p:{page + 1}"))
    if pager:
        rows.append(pager)
    rows.append(nav_row())
    return InlineKeyboardMarkup(rows)


def faq_detail_keyboard(faq_index):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⬅️ Back to FAQ", callback_data="go:faq")],
            nav_row(),
        ]
    )





def ask_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📘 Regulations", callback_data="go:regulations"),
                InlineKeyboardButton("🏆 Awards & Recognition", callback_data="go:awards"),
            ],
            [
                InlineKeyboardButton("📊 Visual Diagrams", callback_data="go:diagrams"),
                InlineKeyboardButton("📅 Calendar", callback_data="quick:calendar"),
            ],
            [
                InlineKeyboardButton("💰 Fees", callback_data="go:fees"),
                InlineKeyboardButton("📞 PPA Contact", callback_data="quick:ppa"),
            ],
            nav_row(),
        ]
    )





def after_regulation_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📘 Academic Regulations Library", callback_data="go:regulations")],
            [
                InlineKeyboardButton("💬 Ask Question", callback_data="go:ask"),
                primary_inline_button("🏠 Main Menu", "go:home"),
            ],
        ]
    )





def after_award_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🏆 Award List Library", callback_data="go:awards")],
            [
                InlineKeyboardButton("💬 Ask Question", callback_data="go:ask"),
                primary_inline_button("🏠 Main Menu", "go:home"),
            ],
        ]
    )


def nlp_choice_keyboard(payload):
    kind = payload.get("kind")
    choices = payload.get("choices") or []
    language = payload.get("language") or "en"
    rows = []

    if kind in {"suggestion", "followup"} and choices:
        rows.extend(numbered_rows(len(choices), "nlp:n:", 0, per_row=4))

    elif kind in {"yesno", "yesno_doc", "after"}:
        for choice in choices:
            key = choice.get("key")
            label = choice.get(language) or choice.get("en") or key
            if key == "yes":
                callback = "nlp:yes"
            elif key == "ask":
                callback = "go:ask"
            elif key == "docs":
                callback = "go:docs"
            elif key == "fees":
                callback = "go:fees"
            elif key == "menu":
                callback = "go:home"
            else:
                callback = f"nlp:k:{key}"
            rows.append([InlineKeyboardButton(label, callback_data=callback)])

    return InlineKeyboardMarkup(rows)





def help_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📖 Interactive User Guide", callback_data="help:topic:guide")],
            [InlineKeyboardButton("⚡ Features & Commands", callback_data="help:topic:features")],
            [InlineKeyboardButton("❓ FAQ & Admin Review System", callback_data="help:topic:faq_info")],
            [InlineKeyboardButton("📞 PPA Contact Directory", callback_data="help:topic:ppa")],
            [
                InlineKeyboardButton("💬 Ask Question", callback_data="go:ask"),
                primary_inline_button("🏠 Main Menu", "go:home"),
            ],
        ]
    )


def after_help_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("ℹ️ Help Center", callback_data="go:help")],
            [
                InlineKeyboardButton("💬 Ask Question", callback_data="go:ask"),
                primary_inline_button("🏠 Main Menu", "go:home"),
            ],
        ]
    )


def feedback_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⭐ 1", callback_data="fb:star:1"),
                InlineKeyboardButton("⭐ 2", callback_data="fb:star:2"),
                InlineKeyboardButton("⭐ 3", callback_data="fb:star:3"),
                InlineKeyboardButton("⭐ 4", callback_data="fb:star:4"),
                InlineKeyboardButton("⭐ 5", callback_data="fb:star:5"),
            ],
            [InlineKeyboardButton("💡 Suggestion / Idea", callback_data="fb:type:suggestion")],
            [InlineKeyboardButton("🐞 Report Bug / Error", callback_data="fb:type:bug")],
            [InlineKeyboardButton("❓ Missing Info Report", callback_data="fb:type:missing_info")],
            [InlineKeyboardButton("❤️ General Praise", callback_data="fb:type:praise")],
            [
                InlineKeyboardButton("👍 Quick Like", callback_data="fb:helpful"),
                InlineKeyboardButton("👎 Needs Improvement", callback_data="fb:not"),
            ],
            nav_row(),
        ]
    )


def after_feedback_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⭐ Feedback Hub", callback_data="go:fb")],
            [
                InlineKeyboardButton("💬 Ask Question", callback_data="go:ask"),
                primary_inline_button("🏠 Main Menu", "go:home"),
            ],
        ]
    )


def academic_regulation_category_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🎓 Credit Transfer (Pindah Kredit)", callback_data="regs:topic:credit_transfer")],
            [InlineKeyboardButton("📝 Course Registration Rules", callback_data="regs:topic:course_registration")],
            [InlineKeyboardButton("📊 GPA, CGPA & Academic Standing", callback_data="regs:topic:academic_standing")],
            [InlineKeyboardButton("🧮 GPA / CGPA Target Calculator", callback_data="calc:gpa:start")],
            [InlineKeyboardButton("📊 Visual Procedure Flowcharts", callback_data="go:diagrams")],
            [InlineKeyboardButton("⏳ Academic Calendar Countdown", callback_data="quick:countdown")],
            [InlineKeyboardButton("🏥 Deferment & Study Withdrawal", callback_data="regs:topic:deferment")],
            [InlineKeyboardButton("📌 Attendance & Exam Regulations", callback_data="regs:topic:attendance")],
            [InlineKeyboardButton("📂 Download Regulation PDF", callback_data="regs:topic:pdf")],
            nav_row(),
        ]
    )


def awards_category_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🎯 Check My Award Eligibility (Quiz)", callback_data="quiz:award:start")],
            [InlineKeyboardButton("🥇 Anugerah Pelajaran Diraja", callback_data="awards:topic:diraja")],
            [InlineKeyboardButton("🏛️ Anugerah Canselor", callback_data="awards:topic:canselor")],
            [InlineKeyboardButton("🎖️ Anugerah Naib Canselor", callback_data="awards:topic:naib_canselor")],
            [InlineKeyboardButton("🎓 Anugerah Alumni", callback_data="awards:topic:alumni")],
            [InlineKeyboardButton("💻 Anugerah PSM Terbaik", callback_data="awards:topic:psm")],
            [InlineKeyboardButton("🏆 Anugerah Tokoh Siswa HEPA", callback_data="awards:topic:tokoh_siswa")],
            [InlineKeyboardButton("💡 Pingat Inovasi & RITEC", callback_data="awards:topic:ritec")],
            [InlineKeyboardButton("📄 Recipients List & Convocation PDF", callback_data="awards:topic:pdf")],
            nav_row(),
        ]
    )


def cgpa_calculator_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⭐ CGPA 3.70 – 4.00 (First Class)", callback_data="calc:gpa:tier:1")],
            [InlineKeyboardButton("⭐ CGPA 3.50 – 3.69 (Dean's List)", callback_data="calc:gpa:tier:2")],
            [InlineKeyboardButton("⭐ CGPA 3.00 – 3.49 (Second Class Upper)", callback_data="calc:gpa:tier:3")],
            [InlineKeyboardButton("⭐ CGPA 2.00 – 2.99 (Second Class Lower)", callback_data="calc:gpa:tier:4")],
            [
                InlineKeyboardButton("📘 Regulations", callback_data="go:regulations"),
                primary_inline_button("🏠 Main Menu", "go:home"),
            ],
        ]
    )


def award_quiz_step1_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🏆 3.70 – 4.00 (First Class)", callback_data="quiz:step1:high")],
            [InlineKeyboardButton("🎖️ 3.50 – 3.69 (Dean's List)", callback_data="quiz:step1:mid")],
            [InlineKeyboardButton("📜 Below 3.50", callback_data="quiz:step1:norm")],
            nav_row(),
        ]
    )


def award_quiz_step2_keyboard(cgpa_tier):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🌍 National / International / MPP", callback_data=f"quiz:step2:{cgpa_tier}:high")],
            [InlineKeyboardButton("🏛️ Faculty / College (MKP) / Club", callback_data=f"quiz:step2:{cgpa_tier}:mid")],
            [InlineKeyboardButton("📚 Academic Focus Only", callback_data=f"quiz:step2:{cgpa_tier}:norm")],
            nav_row(),
        ]
    )


def award_quiz_step3_keyboard(cgpa_tier, lead_tier):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💻 Outstanding / High Innovation", callback_data=f"quiz:step3:{cgpa_tier}:{lead_tier}:yes")],
            [InlineKeyboardButton("📄 Standard Project", callback_data=f"quiz:step3:{cgpa_tier}:{lead_tier}:no")],
            nav_row(),
        ]
    )



def diagram_category_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📌 Carta Alir Pindah Kredit", callback_data="diagram:credit_transfer")],
            [InlineKeyboardButton("📌 Carta Alir Rayuan Peperiksaan Khas", callback_data="diagram:special_exam")],
            [InlineKeyboardButton("📌 Carta Alir Pendaftaran SMAP AUTOREG", callback_data="diagram:autoreg")],
            [InlineKeyboardButton("📌 Carta Alir Penangguhan Pengajian", callback_data="diagram:deferment")],
            nav_row(),
        ]
    )


def after_diagram_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📊 Diagram & Flowchart Center", callback_data="go:diagrams")],
            [
                InlineKeyboardButton("💬 Ask Question", callback_data="go:ask"),
                primary_inline_button("🏠 Main Menu", "go:home"),
            ],
        ]
    )

