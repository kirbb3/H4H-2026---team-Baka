"""
routes.py
Flask API Blueprint for the GovPolicy Hub backend.

Endpoints:
  GET  /api/policies          — paginated, filtered housing programs from MongoDB
  GET  /api/health            — simple liveness check
  GET  /api/saves             — list policy IDs saved by the current user
  POST /api/saves             — save a policy for the current user
  DEL  /api/saves/<id>        — un-save a policy
  GET  /api/subscriptions     — list policy IDs the user subscribed to for email alerts
  POST /api/subscriptions     — subscribe to email alerts for a policy
  DEL  /api/subscriptions/<id>— unsubscribe

Authentication: every saves/subscriptions endpoint requires a Firebase ID token
passed as  Authorization: Bearer <token>.
"""

import re
import os
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from src.data.database.db_connect import search_programs, get_db

import firebase_admin
from firebase_admin import credentials, auth as fb_auth

# ── Firebase Admin initialisation ─────────────────────────────────────────────
# Firebase Admin SDK is used server-side to verify the ID tokens sent by the
# React frontend.  We initialise it lazily (on first request) so a missing
# service-account file doesn't crash the server at startup.

_fb_init = False

def _init_firebase():
    """Initialise the Firebase Admin SDK exactly once per process."""
    global _fb_init
    if not _fb_init and not firebase_admin._apps:
        # Path to the service-account JSON — override via env var in production.
        sa_path = os.environ.get(
            "GOOGLE_APPLICATION_CREDENTIALS",
            os.path.join(os.path.dirname(__file__), "..", "..", "firebase-service-account.json"),
        )
        cred = credentials.Certificate(sa_path)
        firebase_admin.initialize_app(cred)
        _fb_init = True


def _get_uid():
    """
    Extract and verify the Firebase Bearer token from the request headers.
    Returns (uid, None) on success, or (None, error_response) on failure.
    The error_response is a tuple that can be returned directly from a Flask view.
    """
    _init_firebase()
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not token:
        return None, (jsonify({"error": "Missing token"}), 401)
    try:
        decoded = fb_auth.verify_id_token(token)
        return decoded["uid"], None
    except Exception:
        return None, (jsonify({"error": "Invalid token"}), 401)


# All routes are registered on this blueprint with the /api prefix.
api_bp = Blueprint("api", __name__, url_prefix="/api")


# ── Admin-content filter ──────────────────────────────────────────────────────
# Many San Jose council agenda items are purely internal — budget reviews,
# grant amendments, consultant contracts, legislative position letters.
# These are not useful to residents looking for housing help, so we filter
# them out before returning results.  The regex matches against the program
# name (case-insensitive).

_ADMIN_PATTERNS = re.compile(
    "|".join([
        r"\bannual (progress |performance )?report\b",
        r"\bconsolidated annual\b",
        r"\bimplementation (report|plan update)\b",
        r"\bstatus report\b",
        r"\baudit report\b",
        r"\bwork plan\b",
        r"\bmid[- ]year\b",
        r"\bsemi[- ]annual\b",
        r"\bannual action plan\b",
        r"\bmoving to work annual\b",
        r"\bfiscal impact analysis\b",
        r"\bpipeline analysis\b",
        r"\bcomparative analysis\b",
        r"\brevenue measures analysis\b",
        r"\bfinancial feasibility\b",
        r"\bexpenditure plan monitoring\b",
        r"\bmonitoring and reporting\b",
        r"\bgrant fund monitoring\b",
        r"\bprogram development and monitoring\b",
        r"\bgrant agreement (amendment|extension)\b",
        r"\bamendments? to (grant |the )?agreements?\b",
        r"\b(second|third|fourth|fifth) amendment to (the )?agreement\b",
        r"\bconsultant services\b",
        r"\btransfer to (the )?county\b",
        r"\bextension of the declaration\b",
        r"\btask force (reactivation|formation)\b",
        r"\bspending allocations for fiscal year\b",
        r"^\s*(ab|sb)\s+\d+",          # state legislative bill positions, e.g. "AB 1234"
        r"\bdensity assessment\b",     # internal zoning/land-use assessments, not resident-facing
    ]),
    re.IGNORECASE,
)

def _is_user_facing(program: dict) -> bool:
    """Return True if the program name does NOT match any admin-only pattern."""
    return not _ADMIN_PATTERNS.search(program.get("name", ""))


# ── Date parsing ──────────────────────────────────────────────────────────────

# Date formats found across the scraped data sources.
_DATE_FMTS = ["%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%B %d, %Y", "%b %d, %Y"]

def _parse_date(s: str | None) -> datetime:
    """
    Parse a date string into a datetime object for sorting/comparison.
    Tries each known format in order.  Returns datetime.min on failure so
    undated programs sort to the bottom.
    """
    if not s:
        return datetime.min
    for fmt in _DATE_FMTS:
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return datetime.min


# ── Similarity-based deduplication ───────────────────────────────────────────
# The scraper often extracts the same underlying program from multiple council
# meetings with slightly different names (e.g. "Hawthorn Senior Apartments -
# Construction-Permanent Loan..." and "Hawthorn Senior Apartments Loan
# Commitment").  We deduplicate by word-set similarity so only the most recent
# version of each program is shown.

# Common English words that carry no semantic meaning and would pollute the
# similarity score if included.
_STOPWORDS = frozenset({
    "of", "the", "a", "an", "for", "and", "or", "to", "in", "at", "by",
    "from", "with", "is", "its", "are", "on", "as", "be",
})

def _sig_words(name: str) -> frozenset:
    """
    Extract the set of significant (non-stop, length > 2) words from a name.
    Punctuation is stripped so "Santa Clara's" → {"santa", "claras"}.
    """
    s = re.sub(r"[^\w\s]", " ", name.lower())
    return frozenset(w for w in s.split() if len(w) > 2 and w not in _STOPWORDS)

def _are_duplicates(ws_a: frozenset, ws_b: frozenset, threshold: float = 0.85) -> bool:
    """
    Return True if the two word-sets represent the same program.

    Algorithm: take the *shorter* set (the more specific name) and measure
    what fraction of its words appear in the longer set.  If ≥ threshold,
    the longer name is a more detailed description of the same thing.

    Using the shorter set as the denominator means "Hawthorn Senior
    Apartments" (3 words) matches "Hawthorn Senior Apartments Loan
    Commitment" (5 words) at 3/3 = 100 %, while programs that merely share
    a couple of common words won't match.

    Short names (< 3 significant words) require an exact match to avoid
    false positives from generic terms like "Rental Assistance".
    """
    if not ws_a or not ws_b:
        return False
    short, long_ = (ws_a, ws_b) if len(ws_a) <= len(ws_b) else (ws_b, ws_a)
    if len(short) < 3:
        # Too few words to reliably detect similarity — require exact match.
        return ws_a == ws_b
    return len(short & long_) / len(short) >= threshold

def _dedup_programs(programs: list[dict]) -> list[dict]:
    """
    Remove near-duplicate programs, keeping only the most recent version.

    Steps:
    1. Sort all programs most-recent-first so the first representative we
       pick for each group is always the newest.
    2. For each program, compare its significant-word set against every
       already-accepted group representative.  If it's a duplicate, skip it.
    3. Return only the accepted representatives.
    """
    sorted_progs = sorted(
        programs,
        key=lambda p: _parse_date(p.get("date_created")),
        reverse=True,
    )
    groups: list[dict] = []        # accepted (newest) representatives
    group_sets: list[frozenset] = []  # their word-sets, for comparison

    for p in sorted_progs:
        ws = _sig_words(p.get("name", ""))
        # Only add this program if it doesn't match any existing group.
        if not any(_are_duplicates(ws, g) for g in group_sets):
            groups.append(p)
            group_sets.append(ws)
    return groups


# ── Label / status lookup tables ──────────────────────────────────────────────
# These translate internal MongoDB enum values into human-readable strings
# for the frontend.

BENEFIT_TYPE_LABELS = {
    "rent":        "Rental Assistance",
    "homebuyer":   "Homebuyer",
    "development": "Development",
    "emergency":   "Emergency Housing",
    "policy":      "Policy",
    "other":       "Other",
}

STATUS_MAP = {
    "approved":     "Active",
    "proposed":     "Proposed",
    "under_review": "Under Review",
    "denied":       "Denied",
    "unknown":      "Unknown",
}

PROFILE_FLAG_LABELS = {
    "veteran_only":            "For Veterans",
    "senior_only":             "For Seniors",
    "disability_preferred":    "For People with Disabilities",
    "currently_homeless_only": "For Homeless Individuals",
}


# ── Funding helpers ───────────────────────────────────────────────────────────

def parse_funding(s: str | None) -> float | None:
    """
    Parse a funding string like '$3,300,000' into a float.
    Returns None if the string is empty or not numeric after cleaning.
    """
    if not s:
        return None
    cleaned = re.sub(r"[$,\s]", "", str(s))
    try:
        return float(cleaned)
    except ValueError:
        return None


def compute_avg_funding(programs: list[dict]) -> float | None:
    """
    Compute the mean funding amount across all programs that have one.
    Used by transform() to show each program's funding relative to the set.
    """
    amounts = [parse_funding(p.get("funding_amount")) for p in programs]
    amounts = [a for a in amounts if a is not None]
    return sum(amounts) / len(amounts) if amounts else None


# ── Data transform ────────────────────────────────────────────────────────────

def transform(p, profile_flags: dict | None = None, avg_funding: float | None = None):
    """
    Convert a raw MongoDB document into the JSON shape expected by the frontend.

    Args:
        p:             The MongoDB program document.
        profile_flags: Dict of {flag: bool} reflecting which profile checkboxes
                       the user selected (veteran, senior, disability, homeless).
                       Used to determine which targeted_labels to attach.
        avg_funding:   Pre-computed average funding across the result set, used
                       to generate a human-readable "X% above/below average" string.
    """
    benefit_label = BENEFIT_TYPE_LABELS.get(p.get("benefit_type", "other"), "Other")
    status = STATUS_MAP.get(p.get("status", "unknown"), "Unknown")
    desc = p.get("description_plain_english") or ""

    # Build the full "content" string that's shown in the expanded detail view.
    # Eligibility text and funding info are appended if present.
    eligibility = p.get("eligibility") or {}
    raw_eligibility = eligibility.get("raw_text", "") if isinstance(eligibility, dict) else ""

    content = desc
    if raw_eligibility:
        content += f"\n\nEligibility: {raw_eligibility}"
    if p.get("funding_amount"):
        content += f"\n\nFunding: {p['funding_amount']}"

    # ── Targeted label detection ───────────────────────────────────────────
    # When the user has selected profile flags (e.g. "I am a Veteran"), we
    # search the program's full text for relevant keywords so we can badge
    # it with "For Veterans" etc.  We do keyword search rather than relying
    # solely on the pre-computed boolean flags because the scraper doesn't
    # always populate those fields correctly.
    targeted_labels = []
    if profile_flags:
        full_text = " ".join([
            p.get("name", ""),
            desc,
            raw_eligibility,
        ]).lower()

        _KEYWORD_MAP = {
            "veteran_only":            ("veteran", "military", "armed forces", "vash"),
            "senior_only":             ("senior", "elder", "elderly", "age 62", "age 65", "older adult", "aging"),
            "disability_preferred":    ("disabilit", "disabled", "ada ", "accessibility", "special needs", "hopwa"),
            "currently_homeless_only": ("homeless", "unhoused", "unsheltered", "transitional housing"),
        }
        _LABEL_MAP = {
            "veteran_only":            "For Veterans",
            "senior_only":             "For Seniors",
            "disability_preferred":    "For People with Disabilities",
            "currently_homeless_only": "For Homeless Individuals",
        }
        for flag, keywords in _KEYWORD_MAP.items():
            # Only badge it if the user actually selected that profile flag AND
            # the program's text contains at least one matching keyword.
            if profile_flags.get(flag) and any(kw in full_text for kw in keywords):
                targeted_labels.append(_LABEL_MAP[flag])

    # ── Funding % vs average ───────────────────────────────────────────────
    # Shows the user at a glance whether this program's funding is large or
    # small relative to similar programs in the current result set.
    funding_pct_diff = None
    amount = parse_funding(p.get("funding_amount"))
    if amount is not None and avg_funding:
        pct = (amount - avg_funding) / avg_funding * 100
        if abs(pct) < 1:
            funding_pct_diff = "≈ average funding"
        elif pct > 0:
            funding_pct_diff = f"+{pct:.0f}% above average"
        else:
            funding_pct_diff = f"{abs(pct):.0f}% below average"

    return {
        "id":               str(p.get("_id", "")),
        "title":            p.get("name", ""),
        "summary":          desc,
        "content":          content,              # expanded detail text
        "category":         benefit_label,
        "department":       "San Jose City Council",
        "date":             _parse_date(p.get("date_created")).strftime("%Y-%m-%d")
                            if _parse_date(p.get("date_created")) != datetime.min
                            else (p.get("date_created") or ""),
        "status":           status,
        "priority":         "High" if p.get("status") == "approved" else "Medium",
        "tags":             [benefit_label, "San Jose", "Housing"],
        "apply_url":        p.get("apply_url"),
        "effective_date":   p.get("effective_date"),
        "closing_date":     p.get("closing_date"),
        "source_url":       p.get("source_url"),   # agenda / meeting page URL
        "funding_amount":   p.get("funding_amount"),
        "funding_pct_diff": funding_pct_diff,
        "benefit_type":     p.get("benefit_type", "other"),
        "targeted_labels":  targeted_labels,       # badges shown when profile filters active
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@api_bp.route("/policies", methods=["GET"])
def get_policies():
    """
    Return housing programs from MongoDB, filtered and deduplicated.

    Query parameters:
      benefit_type          (repeatable) — filter by type: rent, homebuyer, etc.
      veteran_only          true/false   — user is a veteran
      senior_only           true/false   — user is a senior
      disability_preferred  true/false   — user has a disability
      currently_homeless_only true/false — user is currently homeless
      max_income            float        — annual income cap filter
      household_size        int          — household size filter
    """
    # Parse filter params from the query string.
    benefit_types = request.args.getlist("benefit_type") or None
    veteran_only            = request.args.get("veteran_only") == "true"
    senior_only             = request.args.get("senior_only") == "true"
    disability_preferred    = request.args.get("disability_preferred") == "true"
    currently_homeless_only = request.args.get("currently_homeless_only") == "true"
    max_income    = request.args.get("max_income", type=float)
    household_size = request.args.get("household_size", type=int)

    # Collect the profile flags into a dict for easy passing to helpers.
    profile_flags = {
        "veteran_only":            veteran_only,
        "senior_only":             senior_only,
        "disability_preferred":    disability_preferred,
        "currently_homeless_only": currently_homeless_only,
    }
    any_profile_selected = any(profile_flags.values())

    # Fetch matching programs from MongoDB (city + benefit type + income filters).
    programs = search_programs(
        cities=["San Jose"],
        benefit_types=benefit_types,
        max_income=max_income,
        household_size=household_size,
    )

    # If the user specified profile flags, hide programs that are *exclusively*
    # for a group the user doesn't belong to.
    # Example: a veteran who didn't check "disability" should not see
    # disability-only programs, since those are earmarked for that group.
    if any_profile_selected:
        def is_eligible(p):
            eligibility = p.get("eligibility") or {}
            for flag in profile_flags:
                # If this program requires a flag that the user did NOT select → hide it.
                if eligibility.get(flag) and not profile_flags[flag]:
                    return False
            return True
        programs = [p for p in programs if is_eligible(p)]

    # Remove internal/administrative items residents can't directly use.
    programs = [p for p in programs if _is_user_facing(p)]
    # Collapse near-duplicate program names, keeping the most recent version.
    programs = _dedup_programs(programs)
    # Compute average funding across the final set for the "% above average" labels.
    avg_funding = compute_avg_funding(programs)

    return jsonify([transform(p, profile_flags, avg_funding) for p in programs]), 200


@api_bp.route("/health", methods=["GET"])
def health_check():
    """Simple liveness probe — returns 200 if the server is running."""
    return jsonify({"status": "healthy"}), 200


# ── Saved policies ────────────────────────────────────────────────────────────
# Users can bookmark policies to revisit them.  Saves are stored in the
# `saved_policies` MongoDB collection keyed by (user_id, policy_id).

@api_bp.route("/saves", methods=["GET"])
def get_saves():
    """Return a list of policy IDs saved by the authenticated user."""
    uid, err = _get_uid()
    if err:
        return err
    col = get_db()["saved_policies"]
    docs = col.find({"user_id": uid}, {"policy_id": 1, "_id": 0})
    return jsonify([d["policy_id"] for d in docs]), 200


@api_bp.route("/saves", methods=["POST"])
def add_save():
    """Save a policy for the authenticated user (idempotent upsert)."""
    uid, err = _get_uid()
    if err:
        return err
    policy_id = (request.get_json() or {}).get("policy_id")
    if not policy_id:
        return jsonify({"error": "policy_id required"}), 400
    col = get_db()["saved_policies"]
    # upsert=True means a second save of the same policy is a no-op.
    col.update_one(
        {"user_id": uid, "policy_id": policy_id},
        {"$setOnInsert": {"saved_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return jsonify({"saved": True}), 200


@api_bp.route("/saves/<policy_id>", methods=["DELETE"])
def remove_save(policy_id):
    """Remove a saved policy for the authenticated user."""
    uid, err = _get_uid()
    if err:
        return err
    get_db()["saved_policies"].delete_one({"user_id": uid, "policy_id": policy_id})
    return jsonify({"saved": False}), 200


# ── Email notification subscriptions ─────────────────────────────────────────
# Users can subscribe to email alerts for a policy.  When the policy is
# updated in MongoDB (e.g. by a future scraper run), a notification job can
# query this collection to find who to email.

@api_bp.route("/subscriptions", methods=["GET"])
def get_subscriptions():
    """Return a list of policy IDs the authenticated user is subscribed to."""
    uid, err = _get_uid()
    if err:
        return err
    col = get_db()["subscriptions"]
    docs = col.find({"user_id": uid}, {"policy_id": 1, "_id": 0})
    return jsonify([d["policy_id"] for d in docs]), 200


@api_bp.route("/subscriptions", methods=["POST"])
def add_subscription():
    """Subscribe the authenticated user to email updates for a policy."""
    uid, err = _get_uid()
    if err:
        return err
    policy_id = (request.get_json() or {}).get("policy_id")
    if not policy_id:
        return jsonify({"error": "policy_id required"}), 400

    # Look up the user's email address via Firebase Admin so we can store it
    # alongside the subscription (avoids requiring the client to send it).
    _init_firebase()
    try:
        email = fb_auth.get_user(uid).email
    except Exception:
        email = None

    col = get_db()["subscriptions"]
    col.update_one(
        {"user_id": uid, "policy_id": policy_id},
        {"$setOnInsert": {
            "subscribed_at": datetime.now(timezone.utc),
            "email": email,
        }},
        upsert=True,
    )
    return jsonify({"subscribed": True}), 200


@api_bp.route("/subscriptions/<policy_id>", methods=["DELETE"])
def remove_subscription(policy_id):
    """Unsubscribe the authenticated user from a policy's email alerts."""
    uid, err = _get_uid()
    if err:
        return err
    get_db()["subscriptions"].delete_one({"user_id": uid, "policy_id": policy_id})
    return jsonify({"subscribed": False}), 200
