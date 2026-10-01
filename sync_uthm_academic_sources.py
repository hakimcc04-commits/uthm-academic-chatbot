"""Build a searchable catalog of official UTHM academic web sources.

The catalog deliberately stores source URLs and concise descriptions instead of
training the intent model on copied web-page text. This keeps answers grounded
in the official page and makes future refreshes safe and repeatable.
"""

from __future__ import annotations

import argparse
import csv
import html
import re
import time
from collections import Counter, deque
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = BASE_DIR / "academic_web_sources.csv"
USER_AGENT = "UTHM-Academic-Chatbot-Source-Catalog/1.0 (+academic support)"
TIMEOUT_SECONDS = 20
REQUEST_DELAY_SECONDS = 0.2

SITES = {
    "Pejabat Bendahari UTHM": "https://bendahari.uthm.edu.my/",
    "Pejabat Pengurusan Akademik UTHM": "https://amo.uthm.edu.my/",
    "Portal Rasmi UTHM": "https://www.uthm.edu.my/en/",
}

# Essential student-facing pages are explicitly retained even if a bounded
# crawl reaches its page limit before following every navigation branch.
CURATED_SOURCES = [
    ("Pejabat Pengurusan Akademik UTHM", "Senarai Program Dan Syarat Kemasukan (Diploma & Sarjana Muda)", "program,syarat,kemasukan,admission,diploma,sarjana muda,faculty,fakulti", "https://amo.uthm.edu.my/index.php/kemasukan/warganegara/senarai-dan-syarat-program"),
    ("Pejabat Pengurusan Akademik UTHM", "Tarikh Penting Kemasukan Dan Proses Pendaftaran", "tarikh penting,kemasukan,admission,pendaftaran,registration", "https://amo.uthm.edu.my/index.php/kemasukan/warganegara/tarikh-penting-kemasukan-dan-proses-pendaftaran"),
    ("Pejabat Pengurusan Akademik UTHM", "Berhenti Pengajian", "berhenti pengajian,withdrawal,student,pelajar", "https://amo.uthm.edu.my/index.php/pelajar/pelajar/berhenti-pengajian"),
    ("Pejabat Pengurusan Akademik UTHM", "Tarik Diri Kursus", "tarik diri kursus,withdrawal,course,kursus,student,pelajar", "https://amo.uthm.edu.my/index.php/pelajar/pelajar/tarik-diri-kursus"),
    ("Pejabat Pengurusan Akademik UTHM", "Jadual Waktu Kuliah Akademik", "jadual waktu,kuliah,class schedule,lecture,academic", "https://amo.uthm.edu.my/index.php/pelajar/kuliah/jadual-waktu-kuliah-akademik"),
    ("Pejabat Pengurusan Akademik UTHM", "Peperiksaan Akhir", "peperiksaan akhir,final examination,exam,jadual", "https://amo.uthm.edu.my/index.php/pelajar/peperiksaan/peperiksaan-akhir"),
    ("Pejabat Pengurusan Akademik UTHM", "Senarai Graduan UTHM", "senarai graduan,graduate list,graduation,pengijazahan", "https://amo.uthm.edu.my/index.php/pelajar/pengijazahan/senarai-graduan"),
    ("Pejabat Pengurusan Akademik UTHM", "Surat Pengesahan Penganugerahan", "surat pengesahan,penganugerahan,award confirmation,graduation", "https://amo.uthm.edu.my/index.php/pelajar/pengijazahan/surat-pengesahan-penganugerahan"),
    ("Pejabat Pengurusan Akademik UTHM", "Transkrip Dan Sijil Akademik", "transkrip,sijil akademik,transcript,academic certificate,graduation", "https://amo.uthm.edu.my/index.php/pelajar/pengijazahan/transkrip-dan-sijil-akademik"),
    ("Portal Rasmi UTHM", "Programme Offered", "programme offered,program,admission,undergraduate,postgraduate", "https://www.uthm.edu.my/en/join-us/admission/programmes-offered"),
    ("Portal Rasmi UTHM", "International Students", "international students,admission,student pass,programme", "https://www.uthm.edu.my/en/join-us/admission/international-students"),
    ("Portal Rasmi UTHM", "Part Time Programmes", "part time programmes,program,admission,postgraduate", "https://www.uthm.edu.my/en/join-us/admission/part-time-programmes"),
    ("Portal Rasmi UTHM", "UTHM APEL", "apel,admission,academic,prior experiential learning", "https://www.uthm.edu.my/en/join-us/admission/apel"),
]

ACADEMIC_TERMS = {
    "academic", "akademik", "admission", "kemasukan", "program", "programme",
    "course", "kursus", "registration", "pendaftaran", "exam", "examination",
    "peperiksaan", "calendar", "kalendar", "schedule", "jadual", "graduation",
    "convocation", "pengijazahan", "graduate", "graduan", "transcript", "transkrip",
    "certificate", "sijil", "tuition", "yuran", "fee", "bayaran", "payment",
    "student", "pelajar", "regulation", "peraturan", "smap", "gpa", "cgpa",
    "credit", "kredit", "faculty", "fakulti", "international", "antarabangsa",
    "muet", "lecture", "kuliah", "class", "defer", "tangguh", "withdrawal",
    "berhenti", "add", "drop", "thesis", "research", "penyelidikan",
}

STRONG_ACADEMIC_TERMS = {
    "academic", "akademik", "admission", "kemasukan", "program", "programme",
    "course", "kursus", "exam", "examination", "peperiksaan", "calendar",
    "kalendar", "schedule", "jadual", "graduation", "convocation", "pengijazahan",
    "graduate", "graduan", "transcript", "transkrip", "certificate", "sijil",
    "tuition", "yuran", "student", "pelajar", "regulation", "peraturan", "smap",
    "gpa", "cgpa", "faculty", "fakulti", "muet", "lecture", "kuliah", "thesis",
    "research", "penyelidikan",
}

EXCLUDED_TERMS = {
    "tender", "perolehan", "vendor", "procurement", "asset", "aset", "payroll",
    "gaji", "supplier", "pembekal", "staff", "staf", "kerjaya", "career",
    "syarikat", "company", "sewaan", "rental", "duti", "stamp", "cukai", "tax",
}


@dataclass(frozen=True)
class Link:
    url: str
    text: str


class PageParser(HTMLParser):
    """Extract a page title, readable text, and labelled links."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._in_title = False
        self._href: str | None = None
        self._anchor_text: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "title":
            self._in_title = True
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._anchor_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag == "title":
            self._in_title = False
        if tag == "a" and self._href:
            self.links.append((self._href, " ".join(self._anchor_text)))
            self._href = None
            self._anchor_text = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        cleaned = " ".join(data.split())
        if not cleaned:
            return
        self.text_parts.append(cleaned)
        if self._in_title:
            self.title_parts.append(cleaned)
        if self._href is not None:
            self._anchor_text.append(cleaned)


def normalize_url(url: str) -> str:
    url, _ = urldefrag(url)
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc.lower(), parsed.path, "", parsed.query, ""))


def words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.casefold()))


def is_relevant(text: str) -> bool:
    tokens = words(text)
    if tokens & EXCLUDED_TERMS and not tokens & STRONG_ACADEMIC_TERMS:
        return False
    return bool(tokens & STRONG_ACADEMIC_TERMS)


def is_supported_url(url: str, allowed_host: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() == allowed_host.lower()


def is_pdf(url: str) -> bool:
    return urlparse(url).path.casefold().endswith(".pdf")


def fetch_html(url: str) -> str | None:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                return None
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except (HTTPError, URLError, TimeoutError, ValueError) as error:
        print(f"Skipped {url}: {error}")
        return None


def concise_summary(text: str, title: str) -> str:
    clean = re.sub(r"\s+", " ", html.unescape(text)).strip()
    if not clean:
        return f"Official UTHM academic source: {title}."
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    summary = next((sentence for sentence in sentences if len(sentence) >= 70), clean)
    return summary[:297].rstrip() + ("..." if len(summary) > 297 else "")


def keywords_for(title: str, text: str) -> str:
    tokens = words(f"{title} {text}") & ACADEMIC_TERMS
    ordered = sorted(tokens)
    return ",".join(ordered[:18]) or "academic,uthm"


def record(source_site: str, title: str, text: str, url: str, content_type: str) -> dict[str, str]:
    safe_title = " ".join(title.split()) or "UTHM Academic Information"
    return {
        "document_id": "",
        "document_name": safe_title[:200],
        "keywords": keywords_for(safe_title, text),
        "summary": concise_summary(text, safe_title),
        "source_url": url,
        "file_path": "",
        "source_site": source_site,
        "content_type": content_type,
    }


def crawl_site(source_site: str, seed_url: str, max_pages: int) -> list[dict[str, str]]:
    host = urlparse(seed_url).netloc
    queue: deque[Link] = deque([Link(seed_url, "UTHM academic information")])
    queued = {normalize_url(seed_url)}
    visited: set[str] = set()
    records: list[dict[str, str]] = []

    while queue and len(visited) < max_pages:
        link = queue.popleft()
        url = normalize_url(link.url)
        if url in visited:
            continue
        visited.add(url)
        page = fetch_html(url)
        time.sleep(REQUEST_DELAY_SECONDS)
        if page is None:
            continue

        parser = PageParser()
        parser.feed(page)
        title = " ".join(parser.title_parts) or link.text or source_site
        page_text = " ".join(parser.text_parts)
        relevance_text = f"{title} {link.text} {page_text[:5000]}"
        if url == normalize_url(seed_url) or is_relevant(relevance_text):
            records.append(record(source_site, title, page_text, url, "web_page"))

        for raw_href, anchor_text in parser.links:
            candidate = normalize_url(urljoin(url, raw_href))
            link_text = " ".join(anchor_text.split())
            if not is_supported_url(candidate, host):
                continue
            if not is_relevant(f"{link_text} {candidate}"):
                continue
            if is_pdf(candidate):
                records.append(record(source_site, link_text or Path(urlparse(candidate).path).stem, link_text, candidate, "pdf"))
            elif candidate not in queued and candidate not in visited:
                queue.append(Link(candidate, link_text))
                queued.add(candidate)

    print(f"{source_site}: visited {len(visited)} pages, found {len(records)} academic sources")
    return records


def deduplicate(records: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    unique: dict[str, dict[str, str]] = {}
    for item in records:
        unique.setdefault(item["source_url"], item)
    return sorted(unique.values(), key=lambda item: (item["source_site"], item["document_name"].casefold()))


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync official UTHM academic web-source catalog.")
    parser.add_argument("--max-pages-per-site", type=int, default=35)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.max_pages_per_site < 1:
        raise SystemExit("--max-pages-per-site must be at least 1")

    collected: list[dict[str, str]] = []
    for source_site, url in SITES.items():
        collected.extend(crawl_site(source_site, url, args.max_pages_per_site))

    collected.extend(
        record(source_site, title, keywords, url, "web_page")
        for source_site, title, keywords, url in CURATED_SOURCES
    )

    rows = deduplicate(collected)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]) if rows else [
            "document_id", "document_name", "keywords", "summary", "source_url",
            "file_path", "source_site", "content_type",
        ])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} unique academic sources to {args.output}")
    print("By type:", dict(Counter(row["content_type"] for row in rows)))


if __name__ == "__main__":
    main()
