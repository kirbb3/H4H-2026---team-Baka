"""
Processor
---------
Takes raw housing opportunities from the scraper and saves them to MongoDB.

The scraper outputs a list of dicts. This processor:
  1. Generates a stable slug for each opportunity
  2. Maps scraper fields to the DB schema
  3. Calls upsert_program() so re-runs never create duplicates

Usage (called directly by the scraper, or run standalone):
    python -m src.data.processor
"""

import re
from datetime import datetime, timezone
from src.data.database.db_connect import upsert_program


def make_slug(name: str, date_created: str) -> str:
    """
    Generate a stable, URL-safe slug from the opportunity name + date.
    Example: "Emergency Rental Assistance Fund, 1/15/2026" -> "emergency-rental-assistance-fund-1-15-2026"
    """
    combined = f"{name}-{date_created}"
    slug = combined.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)  # replace non-alphanumeric with dash
    slug = slug.strip("-")
    return slug[:120]  # cap length to avoid absurdly long slugs


def empty_to_none(val: str | None) -> str | None:
    """Convert empty strings and the literal 'None' string (from CSV) to None."""
    if not val or val.strip().lower() == "none":
        return None
    return val.strip()


def map_program_type(program_type: str | None) -> str:
    """Normalize scraper program_type values to db benefit_type values."""
    mapping = {
        "rental_assistance": "rent",
        "homebuyer_grant":   "homebuyer",
        "new_development":   "development",
        "emergency_housing": "emergency",
        "policy":            "policy",
        "other":             "other",
    }
    return mapping.get(program_type or "other", "other")


def parse_eligibility_flags(text: str | None) -> dict:
    """Detect eligibility keywords in raw text to populate boolean flags."""
    if not text:
        return {
            "veteran_only": False,
            "senior_only": False,
            "disability_preferred": False,
            "currently_homeless_only": False,
        }
    t = text.lower()
    return {
        "veteran_only":            any(w in t for w in ("veteran", "military", "armed forces")),
        "senior_only":             any(w in t for w in ("senior", "elder", "age 62", "age 65", "older adult")),
        "disability_preferred":    any(w in t for w in ("disabilit", "disabled", "ada", "accessibility")),
        "currently_homeless_only": any(w in t for w in ("homeless", "unhoused", "unsheltered", "shelter")),
    }


def process_opportunity(raw: dict) -> dict:
    """
    Convert a single raw scraper dict into a MongoDB-ready program document.

    Raw scraper fields:
        opportunity, date_created, program_type, funding_amount,
        eligibility, status, effective_date, apply_url, source_pdf

    DB fields produced:
        slug, name, description_plain_english, benefit_type, status,
        effective_date, apply_url, source_url, funding_amount,
        date_created, authority_level, last_scraped_at, eligibility
    """
    name = raw.get("opportunity") or "Unnamed Program"
    date_created = raw.get("date_created") or "unknown"
    raw_eligibility = raw.get("eligibility")
    raw_description = raw.get("description") or ""

    # Combine description + eligibility text for keyword detection
    combined_text = f"{raw_description} {raw_eligibility or ''}".strip()
    flags = parse_eligibility_flags(combined_text)

    return {
        "slug":                       make_slug(name, date_created),
        "name":                       name,
        "description_plain_english":  raw_description or raw_eligibility or "",
        "benefit_type":               map_program_type(raw.get("program_type")),
        "status":                     raw.get("status") or "unknown",
        "effective_date":             empty_to_none(raw.get("effective_date")),
        "closing_date":               empty_to_none(raw.get("closing_date")),
        "apply_url":                  empty_to_none(raw.get("apply_url")),
        "source_url":                 empty_to_none(raw.get("source_pdf")),
        "funding_amount":             empty_to_none(raw.get("funding_amount")),
        "date_created":               date_created,
        "authority_level":            "city",
        "last_scraped_at":            datetime.now(timezone.utc).isoformat(),
        "eligibility": {
            "raw_text":                raw_eligibility,
            "location_states":         ["CA"],
            "location_cities":         ["San Jose"],
            "income_limit_annual":     None,
            "household_size_max":      None,
            **flags,
        },
    }


def process_and_save(opportunities: list[dict]) -> int:
    """
    Process a list of raw scraper dicts and upsert each into MongoDB.
    Returns the number of documents saved.
    """
    saved = 0
    for raw in opportunities:
        try:
            doc = process_opportunity(raw)
            upsert_program(doc)
            print(f"  [db] Upserted: {doc['slug']}")
            saved += 1
        except Exception as e:
            print(f"  [!] Failed to save '{raw.get('opportunity')}': {e}")
    return saved


# ---------------------------------------------------------------------------
# Standalone: load from CSV and push to MongoDB
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import csv
    import os

    CSV_PATH = os.path.join("housing_opportunities.csv")

    if not os.path.exists(CSV_PATH):
        print(f"No CSV found at {CSV_PATH}. Run the scraper first.")
    else:
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        print(f"Found {len(rows)} row(s) in CSV. Saving to MongoDB...")
        count = process_and_save(rows)
        print(f"\nDone. {count}/{len(rows)} programs saved to MongoDB.")
