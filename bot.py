import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning, module="pydub")

from pathlib import Path
import re
import csv
import html
import math

from telegram import BotCommand, Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

from database import (
    get_or_create_student,
    save_feedback,
    save_query,
    save_response,
    search_faq,
    view_all_faq,
)
from nlp import clean_text, detect_language, get_bot_response, get_last_document_file, get_ui_payload, is_academic_like, last_prediction
from ui import (
    diagram_category_keyboard,
    after_diagram_keyboard,
    DOC_PAGE_SIZE,
    FAQ_PAGE_SIZE,
    MAIN_REPLY,
    academic_regulation_category_keyboard,
    after_document_keyboard,
    after_regulation_keyboard,
    after_award_keyboard,
    after_help_keyboard,
    after_feedback_keyboard,
    ask_keyboard,
    award_quiz_step1_keyboard,
    award_quiz_step2_keyboard,
    award_quiz_step3_keyboard,
    awards_category_keyboard,
    cgpa_calculator_keyboard,
    document_category_keyboard,
    document_list_keyboard,
    faculty_keyboard,
    faq_detail_keyboard,
    faq_list_keyboard,
    feedback_keyboard,
    help_keyboard,
    home_keyboard,
    nlp_choice_keyboard,
    program_keyboard,
    tuition_level_keyboard,
)

import os
BASE_DIR = Path(__file__).resolve().parent
raw_token = os.getenv("TELEGRAM_BOT_TOKEN")
BOT_TOKEN = (raw_token if raw_token and raw_token.strip() else "8808466275:AAGYDm0fEoEPLhYM9ykOr-lnmYyCxl-E6ig").strip()



QUICK_QUESTIONS = {
    "calendar": "academic calendar",
    "register": "course registration",
    "gpa": "what is GPA and CGPA",
    "grad": "graduation eligibility",
    "ppa": "PPA contact",
}

QUESTION_STARTERS = {
    "apa", "adakah", "bagaimana", "bila", "berapa", "boleh", "kenapa", "mana", "saya", "nak",
    "what", "when", "where", "why", "how", "can", "could", "please", "i", "my",
}


def is_reportable_academic_question(user_text):
    """Only send clear, unresolved academic questions to the admin queue.

    Single numbers, menu selections and vague fragments are still retained in the
    activity log, but never ask an admin to review them as knowledge-base gaps.
    """
    cleaned = clean_text(user_text)
    words = cleaned.split()
    junk_words = {
        "1", "2", "3", "4", "5", "6", "7", "8", "9", "0",
        "yes", "no", "ok", "okay", "hi", "hello", "test", "tq", "thanks", "terima kasih", "ya", "tidak"
    }
    if cleaned in junk_words or len(cleaned) < 8 or len(words) < 2 or cleaned.isdigit():
        return False
    return (
        is_academic_like(cleaned)
        or bool(set(words) & QUESTION_STARTERS)
    )


def load_documents():
    documents = []
    with (BASE_DIR / "documents.csv").open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            file_path = str(row.get("file_path", "")).strip()
            if not file_path or file_path.lower() == "nan":
                continue

            resolved_path = Path(file_path)
            if not resolved_path.is_absolute():
                resolved_path = BASE_DIR / resolved_path

            if resolved_path.exists():
                row["resolved_path"] = resolved_path
                documents.append(row)
    return documents


def load_tuition_fees():
    fees_path = BASE_DIR / "tuition_fees.csv"
    if not fees_path.exists():
        return []
    with fees_path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def document_category(document):
    name = str(document.get("document_name", "")).lower()
    if "2025" in name:
        return "archive"
    if any(word in name for word in ("calendar", "kalendar", "takwim", "jadual kerja")):
        return "calendar"
    if name.startswith("borang") or "form" in name:
        return "forms"
    if any(word in name for word in ("tuition", "yuran", "fee")):
        return "fees"
    if any(word in name for word in ("manual", "smap", "regulation", "peraturan")):
        return "guides"
    return "guides"


def filtered_documents(documents, category):
    if not category or category == "all":
        return documents
    filtered = [document for document in documents if document_category(document) == category]
    if category == "fees":
        # Keep the current session ahead of archived fee structures while
        # preserving the official programme order within each session.
        return sorted(
            filtered,
            key=lambda document: 0
            if "2026/2027" in str(document.get("document_name", ""))
            else 1,
        )
    return filtered


def fee_study_level(document):
    """Classify official 2026/2027 fee PDFs from their source title."""
    name = str(document.get("document_name", "")).lower()
    if "diploma" in name:
        return "diploma"
    if "sarjana muda" in name or "bachelor" in name:
        return "bachelor"
    if any(word in name for word in ("phd", "doktor", "doctor")):
        return "phd"
    if "sarjana" in name or "master" in name:
        return "master"
    return ""


def grouped_fees(fees):
    grouped = {}
    for row in fees:
        grouped.setdefault(row["faculty_code"], []).append(row)
    for faculty_code in grouped:
        grouped[faculty_code].sort(key=lambda item: item["program_code"])
    return grouped


def message_target(update: Update):
    if update.callback_query:
        return update.callback_query.message
    return update.message


async def answer_callback(update: Update, text=None):
    if update.callback_query:
        await update.callback_query.answer(text)


def convert_markdown_to_telegram_html(md_text: str) -> str:
    if not md_text:
        return ""
    
    links = []
    def save_link(match):
        label = match.group(1)
        url = match.group(2)
        idx = len(links)
        links.append((label, url))
        return f"___LINK_PLACEHOLDER_{idx}___"
    
    processed = re.sub(r'\[([^\]]+)\]\((https?://[^\s\)]+)\)', save_link, md_text)
    processed = html.escape(processed)
    processed = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', processed)
    processed = re.sub(r'^[ \t]*[\*\-][ \t]+', r'• ', processed, flags=re.MULTILINE)

    for idx, (label, url) in enumerate(links):
        escaped_label = html.escape(label)
        escaped_url = html.escape(url)
        html_link = f'<a href="{escaped_url}">{escaped_label}</a>'
        processed = processed.replace(f"___LINK_PLACEHOLDER_{idx}___", html_link)

    return processed


async def send_html(update: Update, text, reply_markup=None, edit=False):
    kwargs = {
        "text": text,
        "parse_mode": ParseMode.HTML,
        "disable_web_page_preview": True,
        "reply_markup": reply_markup,
    }
    query = update.callback_query
    if edit and query and query.message and query.message.text:
        try:
            await query.edit_message_text(**kwargs)
            return
        except Exception:
            pass
    await message_target(update).reply_text(**kwargs)


async def send_document_file(update: Update, document):
    path = document["resolved_path"]
    caption = f"{document['document_name']}\n\n{document.get('summary', '')}".strip()
    with path.open("rb") as file:
        await message_target(update).reply_document(
            document=file,
            filename=path.name,
            caption=caption[:1024],
            reply_markup=after_document_keyboard(),
        )


async def send_current_calendar_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send the current academic-calendar PDF alongside the Calendar shortcut."""
    calendar = next(
        (
            document
            for document in load_documents()
            if document.get("document_name") == "Academic Calendar"
            and document.get("resolved_path")
        ),
        None,
    )
    if calendar:
        await send_document_file(update, calendar)


def welcome_caption(user):
    username = f"@{user.username}" if user.username else "-"
    return (
        "🎓 <b>UTHM ACADEMIC SUPPORT AI PORTAL</b>\n"
        "<i>Pejabat Pengurusan Akademik (PPA) UTHM • Session 2026/2027</i>\n"
        "Status: 🟢 <b>ONLINE</b> • AI Engine v2.0 Active\n\n"
        "┌──────────────────────────────────────────┐\n"
        "│ 👤 <b>STUDENT IDENTITY BADGE</b>              │\n"
        "├──────────────────────────────────────────┤\n"
        f"│ 🆔 Telegram ID : <code>{user.id}</code>\n"
        f"│ 👤 Student Name : <b>{html.escape(user.full_name or '-')}</b>\n"
        f"│ 🏷️ Handle       : <b>{html.escape(username)}</b>\n"
        "│ 🎓 Status       : <b>Verified Active Student</b>\n"
        "└──────────────────────────────────────────┘\n\n"
        "🚀 <b>QUICK ACCESS ACADEMIC SERVICES</b>\n"
        "├ 📄 <b>Documents Library</b> — 89 Official PDF Forms & Files\n"
        "├ 💰 <b>Tuition Fees</b> — 2026/2027 Programme Fee Schedules\n"
        "├ 📘 <b>Academic Regulations</b> — Rules, Credit Transfer & Attendance\n"
        "├ 🏆 <b>Awards & Recognition</b> — Diraja, Canselor & HEPA Criteria\n"
        "├ 🧮 <b>GPA Target Calculator</b> — Dean's List Simulator\n"
        "├ 📊 <b>Visual Flowcharts</b> — Interactive Procedure Diagrams\n"
        "├ ⏳ <b>Calendar Countdown</b> — Real-Time Milestone Tracker\n"
        "└ ❓ <b>Approved FAQ Hub</b> — Instant Knowledge Search\n\n"
        "👇 <b>Tap a button below or type your question in the chat:</b>"
    )


def clear_wait_states(context: ContextTypes.DEFAULT_TYPE):
    context.user_data["waiting_feedback"] = False
    context.user_data["waiting_feedback_text"] = False
    context.user_data["waiting_document_selection"] = False
    context.user_data["waiting_question"] = False


async def show_home(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    clear_wait_states(context)
    user = update.effective_user
    get_or_create_student(telegram_id=str(user.id), student_name=user.full_name)
    caption = welcome_caption(user)

    query = update.callback_query
    if edit and query and query.message:
        if query.message.text:
            await send_html(update, caption, reply_markup=home_keyboard(), edit=True)
            return
        if query.message.photo:
            try:
                await query.edit_message_caption(
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=home_keyboard(),
                )
                return
            except Exception:
                pass

    target = message_target(update)
    if BANNER_PATH.exists():
        with BANNER_PATH.open("rb") as photo:
            await target.reply_photo(
                photo=photo,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=home_keyboard(),
            )
    else:
        await target.reply_text(
            caption,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=home_keyboard(),
        )

    await target.reply_text(
        "📌 Use the menu bar below anytime. Tap <b>Main Menu</b> to return here.",
        parse_mode=ParseMode.HTML,
        reply_markup=MAIN_REPLY,
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_home(update, context)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    clear_wait_states(context)
    text = (
        "ℹ️ <b>UTHM Academic Assistant Help Center</b>\n"
        "<i>Pejabat Pengurusan Akademik (PPA) UTHM</i>\n\n"
        "Welcome! Tap a <b>help category</b> below to learn how to navigate the system, search academic regulations, or contact the university support desk:\n\n"
        "• <b>📖 User Guide:</b> How to ask questions & use no-typing libraries.\n"
        "• <b>⚡ Features & Commands:</b> System shortcuts & bot capabilities.\n"
        "• <b>❓ FAQ & Admin Review:</b> How unanswered questions get resolved.\n"
        "• <b>📞 PPA Contact:</b> Official phone numbers, email & office location.\n\n"
        "No typing required. Tap a button below."
    )
    await send_html(update, text, reply_markup=help_keyboard(), edit=edit)


async def show_help_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, topic, edit=False):
    details = {
        "guide": (
            "📖 <b>Interactive User Guide & Search Instructions</b>\n\n"
            "1. <b>Asking Questions (Normal Chat):</b>\n"
            "   Type your question naturally in Malay or English. For example:\n"
            "   • <i>\"Berapa yuran pengajian BIT?\"</i>\n"
            "   • <i>\"Apa syarat anugerah canselor?\"</i>\n"
            "   • <i>\"Bagaimana nak mohon pindah kredit?\"</i>\n\n"
            "2. <b>No-Typing Libraries:</b>\n"
            "   • <b>📄 Documents:</b> Tap numbered buttons to receive PDFs.\n"
            "   • <b>📘 Academic Regulations:</b> Interactive guide for credit transfer, grades, and attendance.\n"
            "   • <b>🏆 Penganugerahan:</b> Explore all official UTHM student awards and criteria.\n"
            "   • <b>💰 Tuition Fees:</b> View fee structures by faculty code & degree level."
        ),
        "features": (
            "⚡ <b>System Features & Telegram Commands</b>\n\n"
            "• <code>/start</code> – Launch the assistant & welcome banner.\n"
            "• <code>/menu</code> – Return to the Main Menu anytime.\n"
            "• <code>/help</code> – Open the Help Center.\n"
            "• <code>/regulations</code> – Open Academic Regulation Library.\n"
            "• <code>/awards</code> – Open Award List Library.\n"
            "• <code>/documents</code> – Browse PDF files & forms.\n"
            "• <code>/fees</code> – Browse 2026/2027 tuition fee PDFs.\n"
            "• <code>/faq</code> – Search approved FAQs."
        ),
        "faq_info": (
            "❓ <b>FAQ & Admin Review System</b>\n\n"
            "• <b>Verified Knowledge Base:</b> All responses are fetched from official UTHM Senate guidelines, PPA documents, and faculty portals.\n"
            "• <b>Automated Admin Queue:</b> If you ask an academic question that is not yet in our dataset, the system automatically logs it for PPA Admin review.\n"
            "• <b>Continuous Learning:</b> Once the admin verifies and adds the answer, the chatbot immediately learns to answer that topic for all students."
        ),
        "ppa": (
            "📞 <b>Official PPA Contact Directory</b>\n\n"
            "• 🏢 <b>Office:</b> Pejabat Pengurusan Akademik (PPA), Bangunan Canselori UTHM, 86400 Parit Raja, Batu Pahat, Johor.\n"
            "• 📞 <b>Phone:</b> +607-453 7000 / +607-453 7025\n"
            "• ✉️ <b>Email:</b> ppa@uthm.edu.my\n"
            "• 🌐 <b>Portal:</b> https://ppa.uthm.edu.my\n"
            "• 🎓 <b>Convocation Portal:</b> https://convocation.uthm.edu.my"
        ),
    }

    text = details.get(topic, "Information not available.")
    await send_html(update, text, reply_markup=after_help_keyboard(), edit=edit)


async def show_ask(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    context.user_data["waiting_question"] = True
    context.user_data["waiting_feedback"] = False
    context.user_data["waiting_document_selection"] = False
    text = (
        "💬 <b>Ask an academic question</b>\n\n"
        "Type your question here, or tap a popular topic below.\n\n"
        "<i>Contoh: kalendar akademik, yuran BIT, borang tambah gugur</i>"
    )
    await send_html(update, text, reply_markup=ask_keyboard(), edit=edit)


async def show_document_categories(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    documents = load_documents()
    if not documents:
        await send_html(update, "No local documents are available at the moment.", reply_markup=home_keyboard(), edit=edit)
        return
    context.user_data["document_options"] = documents
    context.user_data["waiting_document_selection"] = True
    text = (
        "📂 <b>Document Library</b>\n\n"
        "Choose a category, then tap the <b>number</b> of the file you need.\n"
        "No typing required."
    )
    await send_html(update, text, reply_markup=document_category_keyboard(), edit=edit)


async def show_document_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page=0, edit=False):
    documents = context.user_data.get("document_options") or load_documents()
    category = context.user_data.get("doc_category", "all")
    visible = filtered_documents(documents, category)
    fee_level = context.user_data.get("fee_level")
    if category == "fees" and fee_level:
        visible = [document for document in visible if fee_study_level(document) == fee_level]
    context.user_data["document_options"] = documents
    context.user_data["visible_documents"] = visible
    context.user_data["waiting_document_selection"] = True

    if not visible:
        await send_html(
            update,
            "No documents in this category yet.",
            reply_markup=document_category_keyboard(),
            edit=edit,
        )
        return

    total_pages = max(1, math.ceil(len(visible) / DOC_PAGE_SIZE))
    page = max(0, min(page, total_pages - 1))
    start = page * DOC_PAGE_SIZE
    page_items = visible[start:start + DOC_PAGE_SIZE]
    context.user_data["doc_page"] = page

    labels = {
        "all": "All Documents",
        "calendar": "Calendar & Schedule",
        "forms": "Academic Forms",
        "guides": "Guides & Regulations",
        "fees": "Tuition Fee PDFs",
        "archive": "Archive 2025/2026",
    }
    fee_labels = {
        "diploma": "Diploma Tuition Fees 2026/2027",
        "bachelor": "Sarjana Muda Tuition Fees 2026/2027",
        "master": "Master Tuition Fees 2026/2027",
        "phd": "PhD Tuition Fees 2026/2027",
    }
    lines = [
        f"📄 <b>{html.escape(fee_labels.get(fee_level, labels.get(category, 'Documents')))}</b>",
        "Tap a <b>number</b> below to receive the file.\n",
    ]
    for offset, document in enumerate(page_items):
        number = start + offset + 1
        summary = str(document.get("summary", "")).strip()
        if len(summary) > 90:
            summary = summary[:87].rstrip() + "..."
        lines.append(
            f"<b>{number}.</b> {html.escape(document['document_name'])}\n"
            f"<i>{html.escape(summary)}</i>"
        )
    lines.append(f"\nPage {page + 1} / {total_pages}")
    await send_html(
        update,
        "\n\n".join(lines),
        reply_markup=document_list_keyboard(page_items, page, total_pages, start),
        edit=edit,
    )


async def deliver_document(update: Update, context: ContextTypes.DEFAULT_TYPE, index):
    visible = context.user_data.get("visible_documents") or context.user_data.get("document_options") or []
    if not 0 <= index < len(visible):
        await send_html(update, "That number is not on this list. Please pick again.", reply_markup=document_category_keyboard())
        return
    document = visible[index]
    context.user_data["waiting_document_selection"] = False
    await send_document_file(update, document)
    await send_html(
        update,
        "✅ <b>Document sent.</b>\nTap below to continue.",
        reply_markup=after_document_keyboard(),
    )


async def show_faculties(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    # The official 2026/2027 PDFs contain the complete local and international
    # fee tables. Send those documents directly instead of showing stale totals.
    documents = load_documents()
    current_fee_documents = [
        document
        for document in documents
        if document_category(document) == "fees"
        and "2026/2027" in str(document.get("document_name", ""))
    ]
    if not current_fee_documents:
        await send_html(update, "Tuition fee documents are not available yet.", reply_markup=home_keyboard(), edit=edit)
        return
    context.user_data["document_options"] = documents
    context.user_data["fee_level"] = None
    context.user_data["waiting_document_selection"] = False
    await send_html(
        update,
        "💳 <b>Tuition Fees 2026/2027</b>\n\n"
        "Choose your <b>study level</b> to see only the official fee PDFs for that programme.",
        reply_markup=tuition_level_keyboard(),
        edit=edit,
    )


async def show_fee_level_documents(update: Update, context: ContextTypes.DEFAULT_TYPE, level, edit=False):
    documents = context.user_data.get("document_options") or load_documents()
    context.user_data["document_options"] = documents
    context.user_data["doc_category"] = "fees"
    context.user_data["fee_level"] = level
    await show_document_page(update, context, page=0, edit=edit)


async def show_faculty_programs(update: Update, context: ContextTypes.DEFAULT_TYPE, faculty_code, edit=False):
    grouped = context.user_data.get("fee_groups") or grouped_fees(load_tuition_fees())
    context.user_data["fee_groups"] = grouped
    programs = grouped.get(faculty_code, [])
    if not programs:
        await show_faculties(update, context, edit=edit)
        return
    faculty_name = programs[0].get("faculty_name", faculty_code)
    lines = [
        f"💰 <b>{html.escape(faculty_code)}</b>",
        f"<i>{html.escape(faculty_name)}</i>\n",
        "Tap a <b>number</b> for programme details.\n",
    ]
    for index, row in enumerate(programs, start=1):
        lines.append(
            f"<b>{index}.</b> <code>{html.escape(row['program_code'])}</code> — "
            f"RM {html.escape(str(row['total_tuition_fee_rm']))}\n"
            f"{html.escape(row['program_name'])}"
        )
    await send_html(
        update,
        "\n\n".join(lines),
        reply_markup=program_keyboard(programs, faculty_code),
        edit=edit,
    )


async def show_program_fee(update: Update, context: ContextTypes.DEFAULT_TYPE, faculty_code, index):
    grouped = context.user_data.get("fee_groups") or grouped_fees(load_tuition_fees())
    programs = grouped.get(faculty_code, [])
    if not 0 <= index < len(programs):
        await show_faculty_programs(update, context, faculty_code)
        return
    row = programs[index]
    text = (
        f"💰 <b>{html.escape(row['program_code'])}</b>\n"
        f"{html.escape(row['program_name'])}\n\n"
        f"Faculty: <code>{html.escape(faculty_code)}</code>\n"
        f"Duration: {html.escape(str(row.get('duration_semesters', '-')))} semesters\n"
        f"Total tuition: <b>RM {html.escape(str(row['total_tuition_fee_rm']))}</b>\n\n"
        "Tap <b>Faculty PDF</b> for the official fee document."
    )
    await send_html(update, text, reply_markup=program_keyboard(programs, faculty_code))


async def send_faculty_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE, faculty_code):
    grouped = context.user_data.get("fee_groups") or grouped_fees(load_tuition_fees())
    programs = grouped.get(faculty_code, [])
    if not programs:
        await show_faculties(update, context)
        return
    file_path = str(programs[0].get("file_path", "")).strip()
    resolved = Path(file_path)
    if not resolved.is_absolute():
        resolved = BASE_DIR / resolved
    if not resolved.exists():
        await send_html(update, "The faculty PDF is not available yet.", reply_markup=faculty_keyboard(sorted(grouped)))
        return
    with resolved.open("rb") as file:
        await message_target(update).reply_document(
            document=file,
            filename=resolved.name,
            caption=f"Tuition fee structure — {faculty_code}",
            reply_markup=after_document_keyboard(),
        )


async def show_academic_regulations(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    clear_wait_states(context)
    text = (
        "📘 <b>Academic Regulation Library</b>\n\n"
        "Choose an academic topic below to view official UTHM rules and procedures, or tap <b>Download Regulation PDF</b> for the full handbook.\n\n"
        "No typing required."
    )
    await send_html(update, text, reply_markup=academic_regulation_category_keyboard(), edit=edit)


async def show_regulation_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, topic, edit=False):
    if topic == "pdf":
        reg_pdf = next(
            (doc for doc in load_documents() if doc.get("document_name") == "Academic Regulation" and doc.get("resolved_path")),
            None
        )
        if reg_pdf:
            await send_document_file(update, reg_pdf)
            await send_html(update, "✅ <b>Official Academic Regulation PDF sent.</b>", reply_markup=after_regulation_keyboard())
        else:
            await send_html(update, "Academic Regulation PDF is not available at the moment.", reply_markup=academic_regulation_category_keyboard(), edit=edit)
        return

    details = {
        "credit_transfer": (
            "🎓 <b>Credit Transfer / Pindah Kredit & Exemption</b>\n\n"
            "• <b>Eligibility:</b> Students transferring from recognized institutions with equivalent course syllabus.\n"
            "• <b>Minimum Grade:</b> Must achieve Grade C (2.00) or higher.\n"
            "• <b>Maximum Credits:</b> Up to 30% of total programme credits can be transferred.\n"
            "• <b>Procedure:</b> Submit the Credit Transfer Form (Borang PPA 08) to the Academic Management Office during registration week.\n\n"
            "<i>Official Source: UTHM Academic Regulations (Edisi Ke-8)</i>"
        ),
        "course_registration": (
            "📝 <b>Course Registration Rules (Peraturan Pendaftaran Kursus)</b>\n\n"
            "• <b>Credit Limit:</b> Minimum 12 credits, Maximum 20 credits per regular semester.\n"
            "• <b>Add/Drop Period:</b> Weeks 1 and 2 of the semester via SMAP AUTOREG system.\n"
            "• <b>Course Withdrawal (TD):</b> Allowed up to Week 8 with approval, subject to minimum credit balance.\n"
            "• <b>Late Registration:</b> Subject to Senat fine and PPA approval.\n\n"
            "<i>Official Source: UTHM Academic Management Office</i>"
        ),
        "academic_standing": (
            "📊 <b>GPA, CGPA & Academic Standing (Kedudukan Akademik)</b>\n\n"
            "• <b>Good Standing (KB - Kedudukan Baik):</b> CGPA >= 2.00 (Pass and eligible to continue studies).\n"
            "• <b>Conditional Probation (KS - Kedudukan Syarat):</b> 1.70 <= CGPA < 2.00 (Allowed maximum 12 credits next semester).\n"
            "• <b>Academic Dismissal (KG - Kedudukan Gagal):</b> CGPA < 1.70 or KS for 2 consecutive semesters.\n"
            "• <b>Grading System:</b> A (4.00), A- (3.70), B+ (3.30), B (3.00), B- (2.70), C+ (2.30), C (2.00).\n\n"
            "<i>Official Source: UTHM Examination & Evaluation Rules</i>"
        ),
        "deferment": (
            "🏥 <b>Deferment & Study Withdrawal (Penangguhan & Penarikan Diri)</b>\n\n"
            "• <b>Medical Deferment:</b> Approved by University Health Centre without affecting maximum duration of study.\n"
            "• <b>Personal/Financial Deferment:</b> Must be applied before Week 4. Allowed for up to 2 semesters maximum.\n"
            "• <b>Quit/Withdrawal:</b> Formal submission via Borang Berhenti Pengajian (Borang PPA 20) with clearance from Library and Bursar.\n\n"
            "<i>Official Source: UTHM Student Affairs & PPA</i>"
        ),
        "attendance": (
            "📌 <b>Attendance & Examination Rules (Syarat Kehadiran & Peperiksaan)</b>\n\n"
            "• <b>Mandatory Attendance:</b> Students MUST achieve at least <b>80% attendance</b> in all lectures, tutorials, and lab sessions.\n"
            "• <b>Barred from Final Exam:</b> Attendance below 80% results in being barred from the final examination with Grade F (0.00).\n"
            "• <b>Special Examination:</b> Granted only for valid medical emergency certified by Government Hospital or University Health Centre.\n\n"
            "<i>Official Source: UTHM Senate Standing Orders</i>"
        ),
    }

    text = details.get(topic, "Information not available.")
    await send_html(update, text, reply_markup=after_regulation_keyboard(), edit=edit)


async def show_awards(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    clear_wait_states(context)
    text = (
        "🏆 <b>Award List Library (Awards & Recognition UTHM)</b>\n\n"
        "Choose an award category below to view eligibility criteria, selection rules, and official details.\n\n"
        "No typing required."
    )
    await send_html(update, text, reply_markup=awards_category_keyboard(), edit=edit)


async def show_award_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, topic, edit=False):
    if topic == "pdf":
        award_pdf = next(
            (doc for doc in load_documents() if "Anugerah Naib Canselor" in doc.get("document_name", "") and doc.get("resolved_path")),
            None
        )
        if award_pdf:
            await send_document_file(update, award_pdf)
            await send_html(update, "✅ <b>Official Award Recipients PDF sent.</b>\nFor full convocation award details, visit https://convocation.uthm.edu.my", reply_markup=after_award_keyboard())
        else:
            await send_html(update, "For full convocation award details, visit https://convocation.uthm.edu.my", reply_markup=after_award_keyboard(), edit=edit)
        return

    details = {
        "diraja": (
            "🥇 <b>Anugerah Pelajaran Diraja (Pingat Jaya Cemerlang)</b>\n\n"
            "• <b>Pengiktirafan:</b> Anugerah tertinggi Majlis Raja-Raja Malaysia khas kepada 2 graduan terbaik (seorang Bumiputera dan seorang Bukan Bumiputera).\n"
            "• <b>Kriteria Utama:</b>\n"
            "  1. CGPA amat cemerlang (Ijazah Kelas Pertama).\n"
            "  2. Penglibatan aktif kokurikulum di peringkat kebangsaan atau antarabangsa.\n"
            "  3. Kualiti kepimpinan dan sahsiah peribadi terpuji.\n\n"
            "<i>Sumber Rasmi: Portal Konvokesyen UTHM</i>"
        ),
        "canselor": (
            "🏛️ <b>Anugerah Canselor UTHM</b>\n\n"
            "• <b>Kelayakan:</b> Dianugerahkan kepada graduan Ijazah Kelas Pertama (CGPA >= 3.70).\n"
            "• <b>Kriteria Utama:</b>\n"
            "  1. Kecemerlangan holistik secara konsisten sepanjang tempoh pengajian.\n"
            "  2. Pencapaian akademik cemerlang dan integriti sahsiah tinggi.\n"
            "  3. Sumbangan aktif dalam aktiviti luar dewan kuliah & universiti.\n\n"
            "<i>Sumber Rasmi: Portal Konvokesyen UTHM</i>"
        ),
        "naib_canselor": (
            "🎖️ <b>Anugerah Naib Canselor UTHM</b>\n\n"
            "• <b>Kelayakan:</b> Graduan Ijazah Kelas Pertama yang dinobatkan sebagai graduan terbaik keseluruhan di dalam fakulti masing-masing.\n"
            "• <b>Kriteria Utama:</b> Menjadi graduan nombor satu (Top Graduate) dalam pencapaian akademik dan prestasi kepimpinan fakulti.\n\n"
            "<i>Sumber Rasmi: Pejabat Pengurusan Akademik (PPA) UTHM</i>"
        ),
        "alumni": (
            "🎓 <b>Anugerah Alumni UTHM</b>\n\n"
            "• <b>Kelayakan:</b> Dianugerahkan kepada graduan yang aktif dalam persatuan/kelab pelajar.\n"
            "• <b>Kriteria Utama:</b> Mempunyai sifat kepimpinan berimpak tinggi serta banyak memberi sumbangan signifikan kepada nama baik universiti.\n\n"
            "<i>Sumber Rasmi: Pusat Kemajuan Alumni UTHM</i>"
        ),
        "psm": (
            "💻 <b>Anugerah Projek Sarjana Muda (PSM) Terbaik</b>\n\n"
            "• <b>Kelayakan:</b> Diberikan oleh setiap fakulti kepada pelajar dengan projek tahun akhir paling cemerlang.\n"
            "• <b>Kriteria Utama:</b>\n"
            "  1. Inovasi teknikal & keaslian idea kajian.\n"
            "  2. Mutu pembangunan perisian / aplikasi mudah alih / seni bina pangkalan data.\n"
            "  3. Keberkesanan integrasi model Machine Learning / Artificial Intelligence.\n\n"
            "<i>Sumber Rasmi: Fakulti Sains Komputer & Teknologi Maklumat (FSKTM) UTHM</i>"
        ),
        "tokoh_siswa": (
            "🏆 <b>Anugerah Tokoh Siswa HEPA (ATS UTHM)</b>\n\n"
            "• <b>Pengiktirafan:</b> Majlis anugerah tahunan untuk mengiktiraf pemimpin pelajar cemerlang.\n"
            "• <b>Kategori Utama:</b> Anugerah Perdana (Tokoh Siswa), Kepimpinan MPP, Kolej Kediaman (MKP), Kelab & Persatuan, Sukarelawan Terbaik, Keusahawanan, Pengucapan Awam/Debat, Sukan (PSU), dan Kebudayaan (PKU).\n\n"
            "<i>Sumber Rasmi: Hal Ehwal Pelajar & Alumni (HEPA) UTHM</i>"
        ),
        "ritec": (
            "💡 <b>Pingat Inovasi & Pertandingan RITEC UTHM</b>\n\n"
            "• <b>Pengiktirafan:</b> Pingat Emas, Perak, dan Gangsa bagi pameran pertandingan inovasi, teknologi, dan reka cipta peringkat universiti (seperti RITEC).\n"
            "• <b>Kriteria Utama:</b> Pembentangan prototaip perisian, kejuruteraan, atau hasil penyelidikan yang berimpak komersial.\n\n"
            "<i>Sumber Rasmi: Pusat Pengurusan Penyelidikan (RMC) & PPA UTHM</i>"
        ),
    }

    text = details.get(topic, "Information not available.")
    await send_html(update, text, reply_markup=after_award_keyboard(), edit=edit)


async def show_cgpa_calculator(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    text = (
        "🧮 <b>UTHM GPA & CGPA Target Simulator</b>\n\n"
        "Select your current CGPA range to calculate the semester GPA required for the <b>Dean's List (Anugerah Dekan)</b> or <b>First Class Honours</b>:\n\n"
        "• <b>Dean's List Requirement:</b> Semester GPA >= 3.50 (min. 12 credit hours).\n"
        "• <b>First Class Honours:</b> Overall CGPA >= 3.70 upon graduation.\n\n"
        "Tap your CGPA range below:"
    )
    await send_html(update, text, reply_markup=cgpa_calculator_keyboard(), edit=edit)


async def show_cgpa_calculator_tier(update: Update, context: ContextTypes.DEFAULT_TYPE, tier, edit=False):
    tier_info = {
        "1": (
            "🥇 <b>Target Analysis: First Class Honours (CGPA 3.70 – 4.00)</b>\n\n"
            "• <b>Status:</b> Outstanding Academic Performance!\n"
            "• <b>Anugerah Dekan Goal:</b> Maintain semester GPA >= 3.50 to earn Dean's List recognition.\n"
            "• <b>Anugerah Canselor / Diraja:</b> You are in the candidate pool! Maintain CGPA >= 3.70 and active leadership involvement.\n\n"
            "<b>Grade Reference:</b>\n"
            "A (4.00), A- (3.70) — Aim for these grades to secure First Class!"
        ),
        "2": (
            "🎖️ <b>Target Analysis: Dean's List Range (CGPA 3.50 – 3.69)</b>\n\n"
            "• <b>Status:</b> High Academic Distinction!\n"
            "• <b>First Class Push:</b> You need approximately 2-3 semesters of GPA >= 3.75 to reach CGPA 3.70.\n"
            "• <b>Anugerah Dekan Goal:</b> Achieve GPA >= 3.50 with min 12 credit hours this semester."
        ),
        "3": (
            "📜 <b>Target Analysis: Second Class Upper (CGPA 3.00 – 3.49)</b>\n\n"
            "• <b>Status:</b> Solid Academic Standing (KB - Kedudukan Baik).\n"
            "• <b>Dean's List Push:</b> Achieve GPA >= 3.50 this semester to qualify for Dean's Award!\n"
            "• <b>Advice:</b> Target A- / B+ grades across 15 credit hours to boost your CGPA."
        ),
        "4": (
            "📘 <b>Target Analysis: Second Class Lower (CGPA 2.00 – 2.99)</b>\n\n"
            "• <b>Status:</b> Pass Standing (KB - Kedudukan Baik).\n"
            "• <b>Improvement Strategy:</b> Repeat key 2-credit or 3-credit subjects with Grade C/D to upgrade your grade point.\n"
            "• <b>Target:</b> Aim for semester GPA >= 3.00 to move into Second Class Upper bracket."
        ),
    }

    text = tier_info.get(tier, "Calculator analysis unavailable.")
    await send_html(update, text, reply_markup=cgpa_calculator_keyboard(), edit=edit)


async def show_academic_countdown(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    now = datetime.now()
    sem1_start = datetime(2026, 9, 21)
    add_drop_deadline = datetime(2026, 10, 4)
    final_exam_start = datetime(2027, 1, 18)

    days_sem1 = (sem1_start - now).days
    days_add_drop = (add_drop_deadline - now).days
    days_exam = (final_exam_start - now).days

    days_sem1_str = f"<b>{days_sem1} days</b>" if days_sem1 > 0 else "Ongoing / Completed"
    days_add_drop_str = f"<b>{days_add_drop} days remaining</b>" if days_add_drop > 0 else "Closed"
    days_exam_str = f"<b>{days_exam} days</b>" if days_exam > 0 else "Ongoing"

    text = (
        "⏳ <b>UTHM Academic Calendar Countdown 2026/2027</b>\n\n"
        f"📅 <b>Semester I Commencement:</b>\n└ {days_sem1_str} (Starts 21 Sept 2026)\n\n"
        f"📝 <b>Add/Drop Course Deadline (Week 2):</b>\n└ {days_add_drop_str} (Closes 4 Oct 2026)\n\n"
        f"✍️ <b>Final Examination Week:</b>\n└ {days_exam_str} (Starts 18 Jan 2027)\n\n"
        "<i>Official Source: Pejabat Pengurusan Akademik (PPA) UTHM</i>"
    )
    await send_html(update, text, reply_markup=after_regulation_keyboard(), edit=edit)


async def show_award_quiz_step1(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    text = (
        "🎯 <b>UTHM Student Award Eligibility Checker</b>\n\n"
        "Answer 3 quick questions to check which official UTHM awards you are eligible for!\n\n"
        "<b>Step 1 of 3:</b> What is your current / expected CGPA?"
    )
    await send_html(update, text, reply_markup=award_quiz_step1_keyboard(), edit=edit)


async def show_award_quiz_step2(update: Update, context: ContextTypes.DEFAULT_TYPE, cgpa_tier, edit=False):
    text = (
        "🎯 <b>UTHM Student Award Eligibility Checker</b>\n\n"
        "<b>Step 2 of 3:</b> What is your Co-curricular / Leadership involvement level?"
    )
    await send_html(update, text, reply_markup=award_quiz_step2_keyboard(cgpa_tier), edit=edit)


async def show_award_quiz_step3(update: Update, context: ContextTypes.DEFAULT_TYPE, cgpa_tier, lead_tier, edit=False):
    text = (
        "🎯 <b>UTHM Student Award Eligibility Checker</b>\n\n"
        "<b>Step 3 of 3:</b> Is your Final Year Project (PSM) rated outstanding or highly innovative?"
    )
    await send_html(update, text, reply_markup=award_quiz_step3_keyboard(cgpa_tier, lead_tier), edit=edit)


async def evaluate_award_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE, cgpa_tier, lead_tier, psm_tier, edit=False):
    eligible = []
    if cgpa_tier == "high" and lead_tier == "high":
        eligible.append("🥇 <b>Anugerah Pelajaran Diraja (Pingat Jaya Cemerlang)</b>")
        eligible.append("🏛️ <b>Anugerah Canselor UTHM</b>")
    if cgpa_tier == "high":
        eligible.append("🎖️ <b>Anugerah Naib Canselor (Top Graduate Faculty)</b>")
    if lead_tier in {"high", "mid"}:
        eligible.append("🎓 <b>Anugerah Alumni UTHM</b>")
        eligible.append("🏆 <b>Anugerah Tokoh Siswa HEPA (ATS UTHM)</b>")
    if psm_tier == "yes":
        eligible.append("💻 <b>Anugerah PSM Terbaik (Best Final Year Project)</b>")
        eligible.append("💡 <b>Pingat Inovasi & Pertandingan RITEC</b>")

    if not eligible:
        eligible_text = "• 📜 You are currently on track for <b>Academic Good Standing (KB)</b>. Aim for GPA >= 3.50 next semester to qualify for the <b>Dean's Award (Anugerah Dekan)</b>!"
    else:
        eligible_text = "\n".join(f"• {item}" for item in eligible)

    text = (
        "🎉 <b>Your Official UTHM Award Eligibility Report</b>\n\n"
        "Based on your profile inputs, here are the awards you qualify for or should aim target:\n\n"
        f"{eligible_text}\n\n"
        "<i>For full criteria details, tap the Award List Library below.</i>"
    )
    await send_html(update, text, reply_markup=after_award_keyboard(), edit=edit)


from semantic_engine import semantic_engine

async def handle_voice_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice
    if not voice:
        return

    try:
        import speech_recognition as sr
        from pydub import AudioSegment
    except ImportError:
        await send_html(update, "🎙️ <i>Voice note processing is currently initializing on the server. Please type your query in text.</i>")
        return

    await send_html(update, "🎙️ <i>Processing your voice note... Please wait a moment.</i>")

    try:
        voice_file = await context.bot.get_file(voice.file_id)
        ogg_path = BASE_DIR / f"temp_voice_{voice.file_id}.ogg"
        wav_path = BASE_DIR / f"temp_voice_{voice.file_id}.wav"

        await voice_file.download_to_drive(custom_path=ogg_path)

        # Convert OGG to WAV
        sound = AudioSegment.from_file(ogg_path)
        sound.export(wav_path, format="wav")

        recognizer = sr.Recognizer()

        with sr.AudioFile(str(wav_path)) as source:
            audio_data = recognizer.record(source)

        try:
            transcribed_text = recognizer.recognize_google(audio_data, language="ms-MY")
        except Exception:
            transcribed_text = recognizer.recognize_google(audio_data, language="en-US")

        # Cleanup temp files
        if ogg_path.exists():
            ogg_path.unlink()
        if wav_path.exists():
            wav_path.unlink()

        caption = f"🎙️ <b>Transkrip Suara:</b>\n<i>\"{html.escape(transcribed_text)}\"</i>\n\n"
        await send_html(update, caption)
        await process_academic_text(update, context, transcribed_text)

    except Exception as err:
        await send_html(update, f"⚠️ Could not transcribe voice note: {html.escape(str(err))}. Please type your question.")


async def show_diagrams(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    clear_wait_states(context)
    text = (
        "📊 <b>Visual Academic Procedure Flowcharts (Carta Alir Prosedur)</b>\n\n"
        "Choose a procedure below to view the official step-by-step visual flowchart diagram:\n\n"
        "• <b>Pindah Kredit Flowchart</b>\n"
        "• <b>Rayuan Peperiksaan Khas Flowchart</b>\n"
        "• <b>AUTOREG SMAP Pendaftaran Flowchart</b>\n"
        "• <b>Penangguhan Pengajian Flowchart</b>\n\n"
        "No typing required."
    )
    await send_html(update, text, reply_markup=diagram_category_keyboard(), edit=edit)


async def show_diagram_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, topic, edit=False):
    diagrams = {
        "credit_transfer": (
            "📊 <b>Carta Alir Permohonan Pindah Kredit</b>\n\n"
            "<code>"
            "┌─────────────────────────────────────────┐\n"
            "│ 1. Pelajar Isi Borang PPA 08            │\n"
            "│    (Borang Permohonan Pindah Kredit)    │\n"
            "└──────────────────┬──────────────────────┘\n"
            "                   │\n"
            "                   ▼\n"
            "┌─────────────────────────────────────────┐\n"
            "│ 2. Lampirkan Transkrip & Silibus Asal   │\n"
            "│    (Gred Minima C / 2.00)               │\n"
            "└──────────────────┬──────────────────────┘\n"
            "                   │\n"
            "                   ▼\n"
            "┌─────────────────────────────────────────┐\n"
            "│ 3. Hantar ke Kaunter PPA / Dekan Fakulti│\n"
            "│    (Sebelum Minggu 2 Semester)          │\n"
            "└──────────────────┬──────────────────────┘\n"
            "                   │\n"
            "                   ▼\n"
            "┌─────────────────────────────────────────┐\n"
            "│ 4. Kelulusan Jawatankuasa Pengajian (JPA)│\n"
            "│    (Semakan Kredit Max 30%)             │\n"
            "└──────────────────┬──────────────────────┘\n"
            "                   │\n"
            "                   ▼\n"
            "┌─────────────────────────────────────────┐\n"
            "│ 5. Keputusan Dikemaskini dalam SMAP     │\n"
            "└─────────────────────────────────────────┘\n"
            "</code>"
        ),
        "special_exam": (
            "📊 <b>Carta Alir Rayuan Peperiksaan Khas</b>\n\n"
            "<code>"
            "┌─────────────────────────────────────────┐\n"
            "│ 1. Kejadian Sakit / Kecemasan Sah       │\n"
            "│    (Sijil Sakit Hospital Kerajaan/PKU)  │\n"
            "└──────────────────┬──────────────────────┘\n"
            "                   │\n"
            "                   ▼\n"
            "┌─────────────────────────────────────────┐\n"
            "│ 2. Kemuka Rayuan dalam Tempoh 48 Jam    │\n"
            "│    ke Pejabat PPA / Timbalan Dekan      │\n"
            "└──────────────────┬──────────────────────┘\n"
            "                   │\n"
            "                   ▼\n"
            "┌─────────────────────────────────────────┐\n"
            "│ 3. Pertimbangan Senat / Jawatankuasa    │\n"
            "└──────────────────┬──────────────────────┘\n"
            "                   │\n"
            "                   ▼\n"
            "┌─────────────────────────────────────────┐\n"
            "│ 4. Jadual Peperiksaan Khas Diterbitkan  │\n"
            "└─────────────────────────────────────────┘\n"
            "</code>"
        ),
        "autoreg": (
            "📊 <b>Carta Alir Pendaftaran Kursus SMAP AUTOREG</b>\n\n"
            "<code>"
            "┌─────────────────────────────────────────┐\n"
            "│ 1. Log Masuk Portal SMAP UTHM           │\n"
            "└──────────────────┬──────────────────────┘\n"
            "                   │\n"
            "                   ▼\n"
            "┌─────────────────────────────────────────┐\n"
            "│ 2. Semak Penasihat Akademik (PA)        │\n"
            "└──────────────────┬──────────────────────┘\n"
            "                   │\n"
            "                   ▼\n"
            "┌─────────────────────────────────────────┐\n"
            "│ 3. Pilih Subjek & Seksyen (12-20 Kredit)│\n"
            "└──────────────────┬──────────────────────┘\n"
            "                   │\n"
            "                   ▼\n"
            "┌─────────────────────────────────────────┐\n"
            "│ 4. Cetak Slip Pendaftaran Kursus        │\n"
            "└─────────────────────────────────────────┘\n"
            "</code>"
        ),
        "deferment": (
            "📊 <b>Carta Alir Penangguhan Pengajian</b>\n\n"
            "<code>"
            "┌─────────────────────────────────────────┐\n"
            "│ 1. Isi Borang Tangguh (Borang PPA 17)   │\n"
            "└──────────────────┬──────────────────────┘\n"
            "                   │\n"
            "                   ▼\n"
            "┌─────────────────────────────────────────┐\n"
            "│ 2. Dapatkan Pengesahan PKU / Kewangan   │\n"
            "└──────────────────┬──────────────────────┘\n"
            "                   │\n"
            "                   ▼\n"
            "┌─────────────────────────────────────────┐\n"
            "│ 3. Hantar ke PPA Sebelum Minggu 4       │\n"
            "└──────────────────┬──────────────────────┘\n"
            "                   │\n"
            "                   ▼\n"
            "┌─────────────────────────────────────────┐\n"
            "│ 4. Surat Kelulusan Penangguhan Diterbit │\n"
            "└─────────────────────────────────────────┘\n"
            "</code>"
        ),
    }

    text = diagrams.get(topic, "Diagram unavailable.")
    await send_html(update, text, reply_markup=after_diagram_keyboard(), edit=edit)


async def show_faq_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page=0, edit=False):
    faqs = view_all_faq()
    if not faqs:
        await send_html(update, "No FAQ information is available at the moment.", reply_markup=home_keyboard(), edit=edit)
        return
    context.user_data["faq_options"] = faqs
    total_pages = max(1, math.ceil(len(faqs) / FAQ_PAGE_SIZE))
    page = max(0, min(page, total_pages - 1))
    start = page * FAQ_PAGE_SIZE
    page_items = faqs[start:start + FAQ_PAGE_SIZE]
    lines = [
        "❓ <b>Frequently Asked Questions</b>",
        "Tap a <b>number</b> to open the answer.\n",
    ]
    for offset, faq in enumerate(page_items):
        faq_id, question, answer, category = faq
        number = start + offset + 1
        lines.append(f"<b>{number}.</b> [{html.escape(str(category))}]\n{html.escape(str(question))}")
    lines.append(f"\nPage {page + 1} / {total_pages}")
    await send_html(
        update,
        "\n\n".join(lines),
        reply_markup=faq_list_keyboard(page_items, page, total_pages, start),
        edit=edit,
    )


async def show_faq_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, index, edit=False):
    faqs = context.user_data.get("faq_options") or view_all_faq()
    if not 0 <= index < len(faqs):
        await show_faq_page(update, context, edit=edit)
        return
    faq_id, question, answer, category = faqs[index]
    text = (
        f"❓ <b>FAQ {index + 1}</b>  [{html.escape(str(category))}]\n\n"
        f"<b>Q:</b> {html.escape(str(question))}\n\n"
        f"<b>A:</b> {html.escape(str(answer))}"
    )
    await send_html(update, text, reply_markup=faq_detail_keyboard(index), edit=edit)


async def show_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    context.user_data["waiting_feedback"] = True
    context.user_data["waiting_feedback_text"] = False
    text = (
        "⭐ <b>UTHM Chatbot Feedback & Rating Center</b>\n\n"
        "Your rating and feedback help us continuously improve academic support for UTHM students!\n\n"
        "<b>1. Tap a Star Rating (1 to 5 Stars)</b>\n"
        "<b>2. Or pick a Feedback Category below</b> to submit suggestions or report an issue."
    )
    await send_html(
        update,
        text,
        reply_markup=feedback_keyboard(),
        edit=edit,
    )


async def record_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE, value, prompt_comment=False):
    user = update.effective_user
    student_id = get_or_create_student(telegram_id=str(user.id), student_name=user.full_name)
    save_feedback(student_id, value)
    context.user_data["waiting_feedback"] = False

    if prompt_comment:
        context.user_data["waiting_feedback_text"] = True
        context.user_data["feedback_type"] = value
        text = (
            f"✅ <b>Feedback Recorded: {html.escape(value)}</b>\n\n"
            "Would you like to type a short comment or detailed description for the PPA Admin team?\n\n"
            "<i>Type your message in the chat box, or tap Main Menu to finish.</i>"
        )
        await send_html(update, text, reply_markup=after_feedback_keyboard(), edit=bool(update.callback_query))
    else:
        context.user_data["waiting_feedback_text"] = False
        text = (
            f"🌟 <b>Thank You! Your feedback ({html.escape(value)}) has been submitted successfully.</b>\n\n"
            "We appreciate your contribution to improving UTHM Academic Support."
        )
        await send_html(update, text, reply_markup=after_feedback_keyboard(), edit=bool(update.callback_query))


async def process_academic_text(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text, edit=False):
    user = update.effective_user
    student_id = get_or_create_student(telegram_id=str(user.id), student_name=user.full_name)
    response_text = get_bot_response(user_text)

    intent = last_prediction.get("intent") or "unmatched"
    if intent == "suggestion_request":
        status = "needs_clarification"
    elif intent == "unmatched":
        status = "unanswered" if is_reportable_academic_question(user_text) else "ignored_non_question"
    else:
        status = "auto_approved"

    if status == "unanswered":
        language = detect_language(user_text)
        faq_match = search_faq(user_text)
        if faq_match:
            source_label = "Sumber: FAQ yang telah disahkan" if language == "bm" else "Source: Approved FAQ"
            response_text = f"{faq_match['answer']}\n\n{source_label}"
            intent = f"faq_{faq_match['category'] or 'general'}"
            status = "auto_approved_faq"
        elif language == "bm":
            response_text += (
                "\n\nSaya sudah rekod soalan ini untuk semakan admin. "
                "Jika soalan ini berkaitan akademik dan admin tambah jawapan rasmi, "
                "chatbot boleh jawab soalan yang sama atau hampir sama selepas itu."
            )
        else:
            response_text += (
                "\n\nI have recorded this question for admin review. "
                "If this is related to UTHM academic information and the admin adds an approved answer, "
                "the chatbot can answer the same or similar question after that."
            )
    elif status == "ignored_non_question":
        language = detect_language(user_text)
        if language == "bm":
            response_text += "\n\nSila taip soalan akademik yang lengkap, contohnya: Berapa yuran pengajian BIT selepas subsidi?"
        else:
            response_text += "\n\nPlease type a complete academic question, for example: What is the BIT tuition fee after subsidy?"

    query_id = save_query(
        student_id=student_id,
        user_question=user_text,
        intent=intent,
        status=status,
    )
    save_response(query_id=query_id, response_text=response_text)

    payload = get_ui_payload()
    markup = nlp_choice_keyboard(payload) if payload.get("kind") else home_keyboard()
    formatted_html = convert_markdown_to_telegram_html(response_text)
    await send_html(update, formatted_html, reply_markup=markup, edit=edit)

    document_file = get_last_document_file()
    if document_file:
        language = detect_language(user_text)
        caption = "Dokumen yang diminta." if language == "bm" else "Here is the requested document."
        with document_file.open("rb") as file:
            await message_target(update).reply_document(
                document=file,
                filename=document_file.name,
                caption=caption,
                reply_markup=after_document_keyboard(),
            )


async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = (update.message.text or "").strip()
    lowered = user_text.lower()

    # Reply-keyboard labels include icons for clarity. Normalize them before
    # routing so a button tap behaves exactly like its text-only equivalent.
    lowered = {
        "💬 ask question": "ask question",
        "📄 documents": "documents",
        "💳 tuition fees": "tuition fees",
        "❓ faq": "faq",
        "ℹ️ help": "help",
        "⭐ feedback": "feedback",
        "🏠 main menu": "main menu",
        "👍 helpful": "helpful",
        "👎 not helpful": "not helpful",
    }.get(lowered, lowered)

    if lowered in {"main menu", "back to menu", "/menu"}:
        await show_home(update, context)
        return

    if context.user_data.get("waiting_feedback_text"):
        comment = (update.message.text or "").strip()
        category = context.user_data.get("feedback_type", "General Comment")
        user = update.effective_user
        student_id = get_or_create_student(telegram_id=str(user.id), student_name=user.full_name)
        save_feedback(student_id, f"{category}: {comment}")
        context.user_data["waiting_feedback_text"] = False
        context.user_data["waiting_feedback"] = False
        text = (
            "✅ <b>Detailed Feedback Saved!</b>\n\n"
            f"<b>Category:</b> {html.escape(category)}\n"
            f"<b>Comment:</b> <i>\"{html.escape(comment)}\"</i>\n\n"
            "Thank you for helping us make UTHM Academic Support better!"
        )
        await send_html(update, text, reply_markup=after_feedback_keyboard())
        return

    if context.user_data.get("waiting_feedback"):
        if lowered in {"helpful", "not helpful"}:
            feedback_text = "Helpful" if lowered == "helpful" else "Not Helpful"
            await record_feedback(update, context, feedback_text)
            return

    if context.user_data.get("waiting_document_selection") and user_text.isdigit():
        await deliver_document(update, context, int(user_text) - 1)
        return

    menu_map = {
        "ask question": show_ask,
        "ask academic question": show_ask,
        "documents": show_document_categories,
        "view documents": show_document_categories,
        "view all documents": show_document_categories,
        "view document": show_document_categories,
        "tuition fees": show_faculties,
        "view tuition fees": show_faculties,
        "view fees": show_faculties,
        "fees": show_faculties,
        "yuran pengajian": show_faculties,
        "lihat yuran": show_faculties,
        "faq": show_faq_page,
        "view faq": show_faq_page,
        "academic regulations": show_academic_regulations,
        "academic regulation": show_academic_regulations,
        "peraturan akademik": show_academic_regulations,
        "regulations": show_academic_regulations,
        "awards & recognition": show_awards,
        "calculator": show_cgpa_calculator,
        "cgpa calculator": show_cgpa_calculator,
        "kalkulator": show_cgpa_calculator,
        "countdown": show_academic_countdown,
        "takwim countdown": show_academic_countdown,
        "quiz": show_award_quiz_step1,
        "award quiz": show_award_quiz_step1,
        "awards": show_awards,
        "anugerah": show_awards,
        "award list": show_awards,
        "senarai anugerah": show_awards,
        "help": help_command,
        "give feedback": show_feedback,
        "feedback": show_feedback,
    }
    action = menu_map.get(lowered)
    if action:
        await action(update, context)
        return

    await process_academic_text(update, context, user_text)


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data or ""
    await answer_callback(update)

    if data in {"go:home", "nav:menu"}:
        await show_home(update, context, edit=True)
        return
    if data == "go:ask":
        await show_ask(update, context, edit=True)
        return
    if data == "go:docs":
        await show_document_categories(update, context, edit=True)
        return
    if data == "go:fees":
        await show_faculties(update, context, edit=True)
        return
    if data == "go:faq":
        await show_faq_page(update, context, edit=True)
        return
    if data == "go:help":
        await help_command(update, context, edit=True)
        return
    if data == "go:diagrams":
        await show_diagrams(update, context, edit=True)
        return
    if data.startswith("diagram:"):
        topic = data.split(":")[-1]
        await show_diagram_detail(update, context, topic, edit=True)
        return
    if data == "go:fb":
        await show_feedback(update, context, edit=True)
        return
    if data == "go:regulations":
        await show_academic_regulations(update, context, edit=True)
        return
    if data == "go:awards":
        await show_awards(update, context, edit=True)
        return
    if data.startswith("regs:topic:"):
        topic = data.split(":")[-1]
        await show_regulation_detail(update, context, topic, edit=True)
        return
    if data.startswith("awards:topic:"):
        topic = data.split(":")[-1]
        await show_award_detail(update, context, topic, edit=True)
        return

    if data == "calc:gpa:start":
        await show_cgpa_calculator(update, context, edit=True)
        return
    if data.startswith("calc:gpa:tier:"):
        tier = data.split(":")[-1]
        await show_cgpa_calculator_tier(update, context, tier, edit=True)
        return

    if data == "quick:countdown":
        await show_academic_countdown(update, context, edit=True)
        return

    if data == "quiz:award:start":
        await show_award_quiz_step1(update, context, edit=True)
        return
    if data.startswith("quiz:step1:"):
        cgpa_tier = data.split(":")[-1]
        await show_award_quiz_step2(update, context, cgpa_tier, edit=True)
        return
    if data.startswith("quiz:step2:"):
        _, _, cgpa_tier, lead_tier = data.split(":")
        await show_award_quiz_step3(update, context, cgpa_tier, lead_tier, edit=True)
        return
    if data.startswith("quiz:step3:"):
        _, _, cgpa_tier, lead_tier, psm_tier = data.split(":")
        await evaluate_award_quiz(update, context, cgpa_tier, lead_tier, psm_tier, edit=True)
        return

    if data == "quick:calendar":
        await process_academic_text(update, context, QUICK_QUESTIONS["calendar"])
        await send_current_calendar_pdf(update, context)
        return

    if data.startswith("quick:"):
        key = data.split(":", 1)[1]
        question = QUICK_QUESTIONS.get(key)
        if question:
            await process_academic_text(update, context, question)
        return

    if data == "docs:cats":
        await show_document_categories(update, context, edit=True)
        return
    if data.startswith("docs:cat:"):
        context.user_data["doc_category"] = data.split(":")[-1]
        await show_document_page(update, context, page=0, edit=True)
        return
    if data.startswith("docs:p:"):
        await show_document_page(update, context, page=int(data.split(":")[-1]), edit=True)
        return
    if data.startswith("docs:i:"):
        await deliver_document(update, context, int(data.split(":")[-1]))
        return

    if data.startswith("fees:fac:"):
        await show_faculty_programs(update, context, data.split(":")[-1], edit=True)
        return
    if data.startswith("fees:level:"):
        await show_fee_level_documents(update, context, data.split(":")[-1], edit=True)
        return
    if data.startswith("fees:pdf:"):
        await send_faculty_pdf(update, context, data.split(":")[-1])
        return
    if data.startswith("fees:i:"):
        _, _, faculty_code, index = data.split(":")
        await show_program_fee(update, context, faculty_code, int(index))
        return

    if data.startswith("faq:p:"):
        await show_faq_page(update, context, page=int(data.split(":")[-1]), edit=True)
        return
    if data.startswith("faq:i:"):
        await show_faq_detail(update, context, int(data.split(":")[-1]), edit=True)
        return

    if data.startswith("help:topic:"):
        topic = data.split(":")[-1]
        await show_help_detail(update, context, topic, edit=True)
        return

    if data.startswith("fb:star:"):
        stars = data.split(":")[-1]
        await record_feedback(update, context, f"Rating: {stars} / 5 Stars", prompt_comment=True)
        return
    if data.startswith("fb:type:"):
        fb_type = data.split(":")[-1]
        labels = {
            "suggestion": "💡 Suggestion / Idea",
            "bug": "🐞 Report Bug / Error",
            "missing_info": "❓ Missing Information",
            "praise": "❤️ General Praise",
        }
        await record_feedback(update, context, labels.get(fb_type, fb_type), prompt_comment=True)
        return
    if data == "fb:helpful":
        await record_feedback(update, context, "Helpful (👍)", prompt_comment=False)
        return
    if data == "fb:not":
        await record_feedback(update, context, "Needs Improvement (👎)", prompt_comment=True)
        return

    if data == "nlp:yes":
        await process_academic_text(update, context, "yes")
        return
    if data.startswith("nlp:n:"):
        number = int(data.split(":")[-1]) + 1
        await process_academic_text(update, context, str(number))
        return


async def view_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_faq_page(update, context)


async def view_documents(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_document_categories(update, context)


async def view_tuition_fees(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_faculties(update, context)


async def view_regulations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_academic_regulations(update, context)


async def view_awards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_awards(update, context)


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_home(update, context)


async def configure_bot_commands(app):
    """Set the concise command menu shown by Telegram beside the message box."""
    await app.bot.set_my_commands(
        [
            BotCommand("start", "Start the academic assistant"),
            BotCommand("menu", "Open the main menu"),
            BotCommand("help", "See how to use the chatbot"),
            BotCommand("regulations", "Browse Academic Regulation Library"),
            BotCommand("awards", "Browse UTHM Awards & Recognition"),
            BotCommand("diagrams", "Visual Academic Procedure Flowcharts"),
            BotCommand("calculator", "GPA / CGPA Target Calculator"),
            BotCommand("countdown", "Academic Calendar Countdown"),
            BotCommand("documents", "Browse academic documents"),
            BotCommand("fees", "View tuition fees"),
            BotCommand("faq", "Browse frequently asked questions"),
        ]
    )


def start_health_check_server():
    port_str = os.getenv("PORT")
    if not port_str:
        return
    try:
        port = int(port_str)
    except ValueError:
        return

    import http.server
    import socketserver
    import threading

    class HealthHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK - UTHM Academic Telegram Bot is active")

        def log_message(self, format, *args):
            pass

    def run_server():
        try:
            server = socketserver.TCPServer(("0.0.0.0", port), HealthHandler)
            print(f"[SYSTEM] Healthcheck HTTP server active on port {port}", flush=True)
            server.serve_forever()
        except Exception as err:
            print(f"[WARNING] Healthcheck server error: {err}", flush=True)

    t = threading.Thread(target=run_server, daemon=True)
    t.start()


def main():
    if BOT_TOKEN == "PASTE_YOUR_NEW_BOT_TOKEN_HERE":
        print("Please insert your new Telegram BotFather token in BOT_TOKEN.")
        return

    start_health_check_server()

    request = HTTPXRequest(
        connect_timeout=60,
        read_timeout=60,
        write_timeout=60,
        pool_timeout=60,
    )
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .request(request)
        .post_init(configure_bot_commands)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("regulations", view_regulations))
    app.add_handler(CommandHandler("awards", view_awards))
    app.add_handler(CommandHandler("diagrams", show_diagrams))
    app.add_handler(CommandHandler("calculator", show_cgpa_calculator))
    app.add_handler(CommandHandler("countdown", show_academic_countdown))
    app.add_handler(CommandHandler("documents", view_documents))
    app.add_handler(CommandHandler("fees", view_tuition_fees))
    app.add_handler(CommandHandler("faq", view_faq))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice_note))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question))
    print("[SYSTEM] UTHM Academic Telegram Bot is running 24/7...", flush=True)
    try:
        app.run_polling(drop_pending_updates=True)
    except ValueError:
        app.run_polling(drop_pending_updates=True, stop_signals=None)


if __name__ == "__main__":
    main()


