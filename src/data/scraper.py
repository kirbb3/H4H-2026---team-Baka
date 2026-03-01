
"""
San Jose City Council Minutes Scraper
--------------------------------------
Runs daily. Visits the Legistar department page, finds all Minutes PDFs,
extracts text, feeds into Claude Haiku (lightweight + cheap), and outputs
a formatted CSV table of housing opportunities found.

Setup:
    pip install playwright beautifulsoup4 requests anthropic pypdf python-dotenv
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
import anthropic
from datetime import datetime
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from pypdf import PdfReader
from io import BytesIO
from playwright.sync_api import sync_playwright

load_dotenv()

# ── CONFIG ────────────────────────────────────────────────────────────────────

TARGET_URL = (
    "https://sanjose.legistar.com/DepartmentDetail.aspx"
    "?ID=21676&GUID=ACCCCFF5-F14A-4E1A-8540-9065F45A8A90&Search=city+council"
)
BASE_URL        = "https://sanjose.legistar.com"
OUTPUT_CSV      = "housing_opportunities.csv"
SEEN_PDFS_FILE  = "seen_pdfs.json"   # tracks already-processed PDFs across runs
MODEL           = "claude-haiku-4-5-20251001"  # lightweight model — fast & cheap

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
]

# ── STEP 1: FETCH THE LEGISTAR PAGE (JS-rendered) ────────────────────────────

def fetch_legistar_page(url: str) -> str:
    """
    Uses Playwright to render the Legistar page, open the Date dropdown,
    select 'Last Year', wait for the table to reload, then return HTML.
    """
    print(f"[1/4] Fetching Legistar page (filtering: Last Year)...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)

        # Click the "Date: Last Year" dropdown button
        page.click("text=Date:")

        # Wait for dropdown options to appear, then click "Last Year"
        page.wait_for_selector("text=Last Year", timeout=5000)
        page.click("text=Last Year")

        # Wait for the table to reload with filtered results
        page.wait_for_load_state("networkidle", timeout=15000)

        html = page.content()
        browser.close()

    return html


# ── STEP 2: PARSE PDF LINKS FROM PAGE ────────────────────────────────────────

def extract_minutes_pdf_links(html: str) -> list[dict]:
    """
    Finds all rows in the Legistar table that contain 'Minutes' and
    returns a list of {date, url} dicts for each PDF link.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    rows = soup.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        row_text = " ".join(c.get_text(strip=True) for c in cells).lower()

        # Only process rows mentioning "minutes"
        if "minutes" not in row_text:
            continue

        # Find any PDF or document links in this row
        for a in row.find_all("a", href=True):
            href = a["href"]
            link_text = a.get_text(strip=True).lower()

            # Match direct PDF links or Legistar viewer links for minutes
            if (
                href.endswith(".pdf")
                or "view.ashx" in href
                or "minutes" in link_text
                or "minutes" in href.lower()
            ):
                full_url = href if href.startswith("http") else BASE_URL + "/" + href.lstrip("/")

                # Try to extract a date from the row text
                date_match = re.search(
                    r"(\d{1,2}/\d{1,2}/\d{2,4}|\w+ \d{1,2},? \d{4})", row_text
                )
                date_str = date_match.group(0) if date_match else "Unknown"

                results.append({"date": date_str, "url": full_url})

    # Deduplicate by URL
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
    """Downloads a PDF and extracts its text content."""
    try:
        resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        reader = PdfReader(BytesIO(resp.content))
        text = "\n".join(
            page.extract_text() or "" for page in reader.pages
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
    """Feeds PDF text into Claude Haiku and extracts structured housing opportunities."""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    chunks = re.split(r'\n(?=\d+\.\d+)', text)
    x = 0
    for chunk in chunks:
        x+=1
        print(chunk)
        print("----------")
        if (x >=3): 
            break
    return []
    all_opportunities = []

    for chunk in chunks:
        prompt = EXTRACTION_PROMPT.format(meeting_date=meeting_date, text=chunk)

        try:
            message = client.messages.create(
                model=MODEL,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text.strip()

            # Strip any accidental markdown code fences
            raw = re.sub(r"```(?:json)?", "", raw).strip()

            opportunities = json.loads(raw)

            if isinstance(opportunities, list):
                for opp in opportunities:
                    opp["source_pdf"] = pdf_url
                all_opportunities.extend(opportunities)

        except json.JSONDecodeError:
            print(f"  [!] LLM returned non-JSON — skipping this chunk")
        except Exception as e:
            print(f"  [!] LLM call failed: {e}")

    return all_opportunities


# ── STEP 5: WRITE TO CSV TABLE ────────────────────────────────────────────────

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

    # 1. Fetch the Legistar page
    html = fetch_legistar_page(TARGET_URL)

    # 2. Find Minutes PDF links
    pdf_links = extract_minutes_pdf_links(html)
    if not pdf_links:
        print("No Minutes PDFs found. Exiting.")
        return

    # 3. Load already-seen PDFs (skip reprocessing)
    seen = load_seen_pdfs()
    new_pdfs = [pdf_links[0]]#[p for p in pdf_links if pdf_fingerprint(p["url"]) not in seen]
    print(f"[2/4] {len(new_pdfs)} new PDF(s) to process (skipping {len(pdf_links) - len(new_pdfs)} already seen)\n")

    # if not new_pdfs:
    #     print("Nothing new today. Run again tomorrow.")
    #     return

    all_opportunities = []

    for i, pdf in enumerate(new_pdfs, 1):
        print(f"[3/4] Processing PDF {i}/{len(new_pdfs)}: {pdf['url']}")

        # Download + extract text
        text = pdf_url_to_text(pdf["url"])
        if not text:
            print("  [!] No text extracted — skipping")
            seen.add(pdf_fingerprint(pdf["url"]))
            continue

        # LLM extraction
        print(f"  Sending to {MODEL} for extraction...")
        opportunities = extract_opportunities_via_llm(text, pdf["date"], pdf["url"])

        if opportunities:
            print(f"  Found {len(opportunities)} housing opportunity/ies")
            all_opportunities.extend(opportunitiesf)
        else:
            print("  No housing opportunities found in this PDF")

        # Mark as seen regardless of result
        seen.add(pdf_fingerprint(pdf["url"]))

    # 4. Write results
    print(f"\n[4/4] Writing results...")
    if all_opportunities:
        append_to_csv(all_opportunities)
    else:
        print("  No new opportunities to write.")

    save_seen_pdfs(seen)

    print(f"\n✓ Done. Results in: {OUTPUT_CSV}")
    print(f"  Total new opportunities found: {len(all_opportunities)}\n")


if __name__ == "__main__":
    print("Hello World.")
    run()