
"""
San Jose City Council Minutes Scraper
--------------------------------------
Fetches meeting minutes from the Legistar city-council page, extracts housing
opportunities via Claude Haiku, then enriches each item by finding the
corresponding staff memorandum through the stable agenda URL and analyzing
its ANALYSIS section for effective_date and apply_url.

Setup:
    pip install playwright beautifulsoup4 requests anthropic pdfplumber python-dotenv
    playwright install chromium

    Create a .env file with:
    ANTHROPIC_API_KEY=your_key_here

Run:
    python scraper.py

Schedule daily (cron):
    0 8 * * * cd /path/to/project && python scraper.py
"""

import os
import re
import csv
import json
import hashlib
import requests
import pdfplumber
import anthropic
from time import sleep
from datetime import datetime
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from io import BytesIO
from playwright.sync_api import sync_playwright
from src.data.database.db_connect import upsert_program, ping as db_ping

load_dotenv()

# ── CONFIG ────────────────────────────────────────────────────────────────────

TARGET_URL = (
    "https://sanjose.legistar.com/DepartmentDetail.aspx"
    "?ID=21676&GUID=ACCCCFF5-F14A-4E1A-8540-9065F45A8A90&Search=city+council"
)
BASE_URL       = "https://sanjose.legistar.com"
OUTPUT_CSV     = "housing_opportunities.csv"
SEEN_PDFS_FILE = "seen_pdfs.json"   # tracks already-processed PDFs across runs
MODEL          = "claude-haiku-4-5-20251001"  # lightweight model — fast & cheap
YEAR           = "2025"  # str(datetime.now().year)


CSV_COLUMNS = [
    "opportunity",
    "date_created",
    "program_type",
    "funding_amount",
    "description",
    "eligibility",
    "status",
    "effective_date",
    "closing_date",
    "apply_url",
    "source_pdf",
    "agenda_url",   # stable city council agenda URL for this meeting
    "memo_url",     # direct link to the staff memorandum PDF for this item
]


# ── STEP 1: FETCH THE LEGISTAR PAGE (JS-rendered) ────────────────────────────

def fetch_legistar_page(url: str) -> str:
    """
    Uses Playwright to render the Legistar page and optionally filter by year.

    The year-filter interaction is best-effort: if the dropdown click fails or
    targets the wrong element, the run continues and relies on the row-level
    year guard in extract_minutes_pdf_links instead.
    """
    print(f"[1/4] Fetching Legistar page (filtering: {YEAR})...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)

        try:
            # Click the "Date:" filter label to open the year dropdown
            page.click("text=Date:", timeout=5000)
            # Use the exact-text locator to avoid matching "1/7/2026" date cells
            page.locator(f"text='{YEAR}'").first.click(timeout=5000)
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            # Year-filter interaction failed — row-level year guard handles filtering
            pass

        html = page.content()
        browser.close()

    return html


# ── STEP 2: PARSE PDF LINKS FROM PAGE ────────────────────────────────────────

def extract_minutes_pdf_links(html: str) -> list[dict]:
    """
    Finds all rows containing both 'minutes' and the target YEAR, and returns:
        {date, url, agenda_url}
    where:
      url        = direct link to the Minutes PDF / view.ashx viewer
      agenda_url = stable link to the Agenda (view.ashx?M=A or similar)

    Meeting-detail page links (MeetingDetail.aspx) are intentionally skipped.
    The YEAR guard here means results are correct even if the Playwright year
    filter in fetch_legistar_page failed to apply.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    rows = soup.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        row_text = " ".join(c.get_text(strip=True) for c in cells).lower()

        if "minutes" not in row_text:
            continue

        # Hard year guard — skip rows that don't belong to the target year
        if YEAR not in row_text:
            continue

        date_match = re.search(
            r"(\d{1,2}/\d{1,2}/\d{2,4}|\w+ \d{1,2},? \d{4})", row_text
        )
        date_str = date_match.group(0) if date_match else "Unknown"

        minutes_url = None
        agenda_url  = None

        for a in row.find_all("a", href=True):
            href      = a["href"]
            link_text = a.get_text(strip=True).lower()
            full_url  = href if href.startswith("http") else BASE_URL + "/" + href.lstrip("/")

            # Skip meeting-detail page links — not stable or useful for end-users
            if "meetingdetail" in href.lower():
                continue

            # Agenda: view.ashx with M=A, or link text contains "agenda"
            if "view.ashx" in href and ("M=A" in href or "agenda" in link_text):
                if agenda_url is None:
                    agenda_url = full_url

            # Minutes PDF: .pdf extension, view.ashx (fallback), or "minutes" in text/href
            elif (
                href.endswith(".pdf")
                or "view.ashx" in href
                or "minutes" in link_text
                or "minutes" in href.lower()
            ):
                if minutes_url is None:
                    minutes_url = full_url

        if minutes_url:
            results.append({
                "date":       date_str,
                "url":        minutes_url,
                "agenda_url": agenda_url,
            })

    # Deduplicate by minutes URL
    seen = set()
    unique = []
    for item in results:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)

    print(f"  Found {len(unique)} Minutes PDF link(s)")
    return unique


# ── STEP 3: DOWNLOAD + EXTRACT TEXT FROM PDF ─────────────────────────────────

def pdf_url_to_text(url: str) -> str | None:
    """Downloads a PDF and extracts its text content using pdfplumber."""
    try:
        resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        with pdfplumber.open(BytesIO(resp.content)) as pdf:
            text = "\n".join(
                page.extract_text() or "" for page in pdf.pages
            )
        return text.strip() if text.strip() else None
    except Exception as e:
        print(f"  [!] Failed to fetch/parse PDF: {e}")
        return None


def pdf_fingerprint(url: str) -> str:
    """Stable ID for a PDF URL so we don't reprocess it."""
    return hashlib.md5(url.encode()).hexdigest()


def load_seen_pdfs() -> set:
    if os.path.exists(SEEN_PDFS_FILE):
        with open(SEEN_PDFS_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen_pdfs(seen: set):
    with open(SEEN_PDFS_FILE, "w") as f:
        json.dump(list(seen), f)


# ── STEP 3b: FIND MEMORANDUM LINK VIA AGENDA PAGE ───────────────────────────

def find_memo_url_via_agenda(agenda_url: str, section_num: str) -> str | None:
    """
    Uses Playwright to navigate the stable agenda URL (e.g. view.ashx?M=A).
    Legistar renders this as an eAgenda HTML viewer with clickable items.
    Searches for a memorandum / staff-report link associated with the given
    agenda section number (e.g. "5.3").

    Falls back to pdfplumber annotation extraction if the page serves a raw PDF.
    Returns the memorandum URL, or None if not found.
    """
    print(f"    Searching agenda for memo at section {section_num}")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page    = browser.new_page()

            # Capture any PDF response URLs in case the agenda redirects to a PDF
            pdf_urls: list[str] = []

            def on_response(response):
                ct = response.headers.get("content-type", "")
                if "pdf" in ct or response.url.lower().endswith(".pdf"):
                    pdf_urls.append(response.url)

            page.on("response", on_response)
            page.goto(agenda_url, wait_until="networkidle", timeout=30000)
            html = page.content()
            browser.close()
    except Exception as e:
        print(f"    [!] Playwright agenda navigation failed: {e}")
        return None

    # --- Search the rendered HTML page for memo links near section_num ---
    soup            = BeautifulSoup(html, "html.parser")
    section_pattern = re.compile(r'\b' + re.escape(section_num) + r'\b')

    for row in soup.find_all("tr"):
        row_text = row.get_text(separator=" ", strip=True)
        if not section_pattern.search(row_text):
            continue
        for a in row.find_all("a", href=True):
            href      = a["href"]
            link_text = a.get_text(strip=True).lower()
            if any(kw in link_text for kw in
                   ("memo", "memorandum", "staff report", "report", "attachment")):
                return href if href.startswith("http") else BASE_URL + "/" + href.lstrip("/")

    # --- Fallback: extract embedded hyperlinks from the agenda PDF ---
    if pdf_urls:
        return _find_memo_link_in_pdf(pdf_urls[-1], section_num)

    print(f"    [!] No memo link found for section {section_num} in agenda")
    return None


def _find_memo_link_in_pdf(pdf_url: str, section_num: str) -> str | None:
    """
    Uses pdfplumber to extract hyperlink annotations from the agenda PDF
    and return a memorandum URL that appears near section_num in the text.
    """
    try:
        resp = requests.get(pdf_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        with pdfplumber.open(BytesIO(resp.content)) as pdf:
            for pdf_page in pdf.pages:
                page_text = pdf_page.extract_text() or ""
                annots    = pdf_page.annots or []

                # Only consider pages where the section number appears
                if section_num not in page_text:
                    continue

                for annot in annots:
                    uri = annot.get("uri") or annot.get("URI")
                    if not uri:
                        continue
                    # Filter for plausible memorandum / Legistar document links
                    if any(kw in uri.lower() for kw in
                           ("memo", "legistar", "view.ashx", "document", "legislation")):
                        return uri
    except Exception as e:
        print(f"    [!] PDF annotation extraction failed: {e}")

    return None


# ── STEP 3c: ANALYZE MEMORANDUM — ANALYSIS SECTION ONLY ──────────────────────

MEMO_ANALYSIS_PROMPT = """
You are reviewing the ANALYSIS section of a San Jose City Council staff memorandum
about a housing program or policy.

Extract exactly two fields:
1. effective_date — When does the policy or program officially take effect?
   Use the date as written (e.g. "July 1, 2026"). Set to null if not explicitly stated.
2. apply_url — A URL where a resident can apply for or learn more about the program.
   The URL MUST appear verbatim in the text. Set to null if no URL is present.

Return ONLY a JSON object — no markdown, no explanation:
{{"effective_date": "...", "apply_url": "..."}}

ANALYSIS SECTION TEXT:
{text}
"""


def analyze_memorandum_analysis_section(memo_url: str, client: anthropic.Anthropic) -> dict:
    """
    Downloads a memorandum PDF, splits it into sections delimited by
    \\n\\n followed by an ALL-CAPS header (e.g. BACKGROUND, ANALYSIS,
    RECOMMENDATION), then sends the ANALYSIS section to the LLM to
    extract effective_date and apply_url.
    """
    text = pdf_url_to_text(memo_url)
    if not text:
        return {}

    # Split on blank line + ALL-CAPS section header
    # e.g. "\n\nANALYSIS\n", "\n\nFISCAL IMPACT\n", "\n\nRECOMMENDATION\n"
    section_chunks = re.split(r'\n\n(?=[A-Z][A-Z\s,\.\-\:]{1,60}(?:\n|$))', text)

    analysis_chunk: str | None = None
    for chunk in section_chunks:
        if re.match(r'ANALYSIS\b', chunk.strip(), re.IGNORECASE):
            analysis_chunk = chunk
            break

    if not analysis_chunk:
        print(f"    [!] No ANALYSIS section found in memorandum: {memo_url}")
        return {}

    prompt = MEMO_ANALYSIS_PROMPT.format(text=analysis_chunk[:6000])

    try:
        message = client.messages.create(
            model=MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        raw = re.sub(r"```(?:json)?", "", raw).strip()
        result = json.loads(raw)
        return result if isinstance(result, dict) else {}
    except Exception as e:
        print(f"    [!] Memorandum analysis failed: {e}")
        return {}


# ── STEP 4: EXTRACT OPPORTUNITIES VIA LLM ────────────────────────────────────

EXTRACTION_PROMPT = """
You are a housing policy analyst reviewing San Jose City Council meeting minutes.

Your ONLY job is to extract agenda items directly about HOUSING.

INCLUDE:
- Affordable housing developments or projects
- Rental assistance or subsidy programs
- Homebuyer grants or down payment assistance
- Emergency housing or shelter funding
- Below Market Rate (BMR) housing programs
- Housing bonds, levies, or dedicated housing funds
- Zoning or policy changes whose PRIMARY purpose is housing

EXCLUDE (ignore completely):
- Roads, parks, transportation, utilities
- General budget items not specific to housing
- Non-housing business permits or contracts
- Public safety, police, fire
- Anything where housing is only mentioned in passing

For each qualifying item, return a JSON array:
[
  {{
    "opportunity": "specific name of the housing item",
    "date_created": "meeting date",
    "program_type": "one of: rental_assistance | homebuyer_grant | new_development | emergency_housing | policy | other",
    "funding_amount": "dollar amount if stated, else null",
    "description": "2-3 sentence plain-English summary of what this program does and who it helps",
    "eligibility": "who qualifies or income limits if stated, else null",
    "status": "one of: approved | proposed | under_review | denied | unknown",
    "effective_date": "date the policy/program takes effect if explicitly stated, else null",
    "closing_date": "application deadline or program end date if explicitly stated, else null",
    "apply_url": "application or program website URL if explicitly stated, else null"
  }}
]

Rules:
- Return ONLY valid JSON — no explanation, no markdown, no code blocks
- If NO housing items are found, return exactly: []
- Never invent details not explicitly stated in the text
- Never guess or construct URLs — only include apply_url if a link appears verbatim in the text

MEETING DATE: {meeting_date}

MINUTES TEXT:
{text}
"""


def extract_opportunities_via_llm(
    text: str, meeting_date: str, pdf_url: str
) -> list[dict]:
    """
    Splits meeting-minutes text into chunks at each agenda section number
    (e.g. "2.3", "10.1") and sends each chunk separately to Claude Haiku
    for housing opportunity extraction.

    Each opportunity is tagged with '_section_num' for memorandum lookup;
    the field is stripped before CSV output.
    """
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Split at newline followed by a section number (digit.digit, e.g. "5.3")
    chunks = re.split(r'\n(?=\d+\.\d+)', text)
    all_opportunities = []

    for chunk in chunks:
        sec_match   = re.match(r'(\d{1,2}\.\d{1,3})', chunk.strip())
        section_num = sec_match.group(1) if sec_match else None

        prompt = EXTRACTION_PROMPT.format(meeting_date=meeting_date, text=chunk)

        try:
            message = client.messages.create(
                model=MODEL,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text.strip()
            raw = re.sub(r"```(?:json)?", "", raw).strip()
            opportunities = json.loads(raw)

            if isinstance(opportunities, list):
                for opp in opportunities:
                    opp["source_pdf"]   = pdf_url
                    opp["_section_num"] = section_num  # internal — stripped before CSV
                all_opportunities.extend(opportunities)

        except json.JSONDecodeError:
            print(f"  [!] LLM returned non-JSON — skipping this chunk")
        except Exception as e:
            print(f"  [!] LLM call failed: {e}")

    return all_opportunities


# ── STEP 5: TRANSFORM + UPSERT TO MONGODB ────────────────────────────────────

# Maps the LLM's program_type value to the benefit_type key used in MongoDB
_BENEFIT_TYPE_MAP = {
    "rental_assistance": "rent",
    "homebuyer_grant":   "homebuyer",
    "new_development":   "development",
    "emergency_housing": "emergency",
    "policy":            "policy",
    "other":             "other",
}


def _make_slug(name: str) -> str:
    """Convert a program name to a URL-safe slug used as the MongoDB unique key."""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _opp_to_mongo_doc(opp: dict) -> dict:
    """
    Transform a scraped opportunity dict (CSV-shaped) into the MongoDB document
    format expected by the programs collection and the /api/policies route.
    """
    name = opp.get("opportunity") or ""
    return {
        "slug":                    _make_slug(name),
        "name":                    name,
        "description_plain_english": opp.get("description") or "",
        "benefit_type":            _BENEFIT_TYPE_MAP.get(
                                       opp.get("program_type", "other"), "other"
                                   ),
        "status":                  opp.get("status") or "unknown",
        "funding_amount":          opp.get("funding_amount"),
        "effective_date":          opp.get("effective_date"),
        "closing_date":            opp.get("closing_date"),
        "apply_url":               opp.get("apply_url"),
        # memo_url is the direct link to the staff memorandum PDF — the most
        # specific government document about this particular policy item.
        # source_url is the broader meeting agenda page, used as a fallback.
        "memo_url":                opp.get("memo_url"),
        "source_url":              opp.get("agenda_url") or opp.get("source_pdf"),
        "date_created":            opp.get("date_created"),
        "eligibility": {
            "raw_text":               opp.get("eligibility") or "",
            "location_states":        ["CA"],
            "location_cities":        ["San Jose"],
            "income_limit_annual":    None,
            "household_size_max":     None,
            "veteran_only":           False,
            "senior_only":            False,
            "disability_preferred":   False,
            "currently_homeless_only": False,
        },
    }


def upsert_opportunities_to_mongo(opportunities: list[dict]) -> int:
    """
    Transform and upsert a list of opportunity dicts into MongoDB.
    Returns the number of documents upserted.
    """
    if not db_ping():
        print("  [!] MongoDB unreachable — skipping database upsert")
        return 0

    count = 0
    for opp in opportunities:
        doc = _opp_to_mongo_doc(opp)
        upsert_program(doc)
        count += 1

    print(f"  Upserted {count} document(s) to MongoDB")
    return count


def upload_csv_to_mongo(csv_path: str = OUTPUT_CSV) -> int:
    """
    Read the housing_opportunities CSV and upsert every row into MongoDB.
    Useful for back-filling the database from an existing CSV.
    """
    if not os.path.exists(csv_path):
        print(f"[upload_csv_to_mongo] File not found: {csv_path}")
        return 0

    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"[upload_csv_to_mongo] Upserting {len(rows)} row(s) from {csv_path}...")
    return upsert_opportunities_to_mongo(rows)


# ── STEP 6: WRITE TO CSV TABLE ────────────────────────────────────────────────

def append_to_csv(rows: list[dict]):
    """Appends new rows to the CSV. Creates file with headers if it doesn't exist."""
    file_exists = os.path.exists(OUTPUT_CSV)

    with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)

    print(f"  Wrote {len(rows)} row(s) to {OUTPUT_CSV}")


# ── MAIN ORCHESTRATOR ─────────────────────────────────────────────────────────

def run():
    print(f"\n=== San Jose Housing Scraper — {datetime.now().strftime('%Y-%m-%d %H:%M')} ===\n")

    if not os.getenv("ANTHROPIC_API_KEY"):
        raise ValueError("ANTHROPIC_API_KEY not set. Add it to your .env file.")

    # 1. Fetch the Legistar department page
    html = fetch_legistar_page(TARGET_URL)

    # 2. Find Minutes PDF links (also captures stable agenda_url)
    pdf_links = extract_minutes_pdf_links(html)
    if not pdf_links:
        print("No Minutes PDFs found. Exiting.")
        return

    # 3. Load already-seen PDFs (skip reprocessing)
    seen = set() #  load_seen_pdfs()
    new_pdfs = [p for p in pdf_links if pdf_fingerprint(p["url"]) not in seen]
    print(f"[2/4] {len(new_pdfs)} new PDF(s) to process "
          f"(skipping {len(pdf_links) - len(new_pdfs)} already seen)\n")

    if not new_pdfs:
        print("Nothing new today. Run again tomorrow.")
        return

    all_opportunities = []

    for i, pdf in enumerate(new_pdfs, 1):
        print(f"[3/4] Processing PDF {i}/{len(new_pdfs)}: {pdf['url']}")

        # Download + extract text from the minutes PDF
        text = pdf_url_to_text(pdf["url"])
        if not text:
            print("  [!] No text extracted — skipping")
            seen.add(pdf_fingerprint(pdf["url"]))
            continue

        # LLM: extract housing opportunities, each tagged with its section number
        print(f"  Sending to {MODEL} for extraction...")
        opportunities = extract_opportunities_via_llm(text, pdf["date"], pdf["url"])

        # ── MEMORANDUM ENRICHMENT ──────────────────────────────────────────────
        # For each housing item, navigate the agenda URL with Playwright to find
        # the corresponding memorandum, then analyze its ANALYSIS section to
        # fill in effective_date and apply_url.
        memo_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        agenda_url  = pdf.get("agenda_url")

        for opp in opportunities:
            section = opp.pop("_section_num", None)

            # Stamp the stable agenda URL on every opportunity
            if agenda_url:
                opp["agenda_url"] = agenda_url

            if section and agenda_url:
                print(f"  Enriching section {section} via agenda URL...")
                memo_url = find_memo_url_via_agenda(agenda_url, section)

                if memo_url:
                    # Save the memo URL so the frontend can link directly to the
                    # government staff report rather than the generic agenda page.
                    opp["memo_url"] = memo_url
                    print(f"    Analyzing memorandum ANALYSIS section: {memo_url}")
                    result = analyze_memorandum_analysis_section(memo_url, memo_client)

                    if result.get("effective_date") and not opp.get("effective_date"):
                        opp["effective_date"] = result["effective_date"]
                        print(f"      → effective_date: {result['effective_date']}")

                    if result.get("apply_url") and not opp.get("apply_url"):
                        opp["apply_url"] = result["apply_url"]
                        print(f"      → apply_url: {result['apply_url']}")
        # ──────────────────────────────────────────────────────────────────────

        if opportunities:
            print(f"  Found {len(opportunities)} housing opportunity/ies")
            all_opportunities.extend(opportunities)
        else:
            print("  No housing opportunities found in this PDF")

        # Mark as seen regardless of result
        seen.add(pdf_fingerprint(pdf["url"]))

    # 4. Write results
    print(f"\n[4/4] Writing results...")
    if all_opportunities:
        append_to_csv(all_opportunities)
        upsert_opportunities_to_mongo(all_opportunities)
    else:
        print("  No new opportunities to write.")

    save_seen_pdfs(seen)

    print(f"\n✓ Done. Results in: {OUTPUT_CSV}")
    print(f"  Total new opportunities found: {len(all_opportunities)}\n")


if __name__ == "__main__":
    print("Hello World.")
    run()

    # Update weekly.
    while True:
        sleep(24 * 3600)
        run()
