import re
import os
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from src.data.database.db_connect import search_programs, get_db

import firebase_admin
from firebase_admin import credentials, auth as fb_auth

# Initialise Firebase Admin once (service account file must exist)
_fb_init = False
def _init_firebase():
    global _fb_init
    if not _fb_init and not firebase_admin._apps:
        sa_path = os.environ.get(
            "GOOGLE_APPLICATION_CREDENTIALS",
            os.path.join(os.path.dirname(__file__), "..", "..", "firebase-service-account.json"),
        )
        cred = credentials.Certificate(sa_path)
        firebase_admin.initialize_app(cred)
        _fb_init = True

def _get_uid():
    """Verify Bearer token and return Firebase UID, or raise 401."""
    _init_firebase()
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not token:
        return None, (jsonify({"error": "Missing token"}), 401)
    try:
        decoded = fb_auth.verify_id_token(token)
        return decoded["uid"], None
    except Exception:
        return None, (jsonify({"error": "Invalid token"}), 401)

api_bp = Blueprint("api", __name__, url_prefix="/api")

# ── Admin-content filter ─────────────────────────────────────────────────────
# Exclude policies that are purely administrative and don't directly help users:
# reports, contract amendments, studies, budget reviews, legislative positions.
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
        r"^\s*(ab|sb)\s+\d+",          # state legislative positions
    ]),
    re.IGNORECASE,
)

def _is_user_facing(program: dict) -> bool:
    return not _ADMIN_PATTERNS.search(program.get("name", ""))

_DATE_FMTS = ["%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%B %d, %Y", "%b %d, %Y"]

def _parse_date(s: str | None) -> datetime:
    """Parse a date string into a datetime for comparison. Returns datetime.min on failure."""
    if not s:
        return datetime.min
    for fmt in _DATE_FMTS:
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return datetime.min

_STOPWORDS = frozenset({
    "of", "the", "a", "an", "for", "and", "or", "to", "in", "at", "by",
    "from", "with", "is", "its", "are", "on", "as", "be",
})

def _sig_words(name: str) -> frozenset:
    s = re.sub(r"[^\w\s]", " ", name.lower())
    return frozenset(w for w in s.split() if len(w) > 2 and w not in _STOPWORDS)

def _are_duplicates(ws_a: frozenset, ws_b: frozenset, threshold: float = 0.85) -> bool:
    if not ws_a or not ws_b:
        return False
    short, long_ = (ws_a, ws_b) if len(ws_a) <= len(ws_b) else (ws_b, ws_a)
    if len(short) < 3:
        return ws_a == ws_b
    return len(short & long_) / len(short) >= threshold

def _dedup_programs(programs: list[dict]) -> list[dict]:
    """Keep only the most recent program per similarity group."""
    sorted_progs = sorted(
        programs,
        key=lambda p: _parse_date(p.get("date_created")),
        reverse=True,
    )
    groups: list[dict] = []
    group_sets: list[frozenset] = []
    for p in sorted_progs:
        ws = _sig_words(p.get("name", ""))
        if not any(_are_duplicates(ws, g) for g in group_sets):
            groups.append(p)
            group_sets.append(ws)
    return groups

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


def parse_funding(s: str | None) -> float | None:
    """Parse a funding string like '$3,300,000' into a float, or None."""
    if not s:
        return None
    cleaned = re.sub(r"[$,\s]", "", str(s))
    try:
        return float(cleaned)
    except ValueError:
        return None


def compute_avg_funding(programs: list[dict]) -> float | None:
    amounts = [parse_funding(p.get("funding_amount")) for p in programs]
    amounts = [a for a in amounts if a is not None]
    return sum(amounts) / len(amounts) if amounts else None


def transform(p, profile_flags: dict | None = None, avg_funding: float | None = None):
    benefit_label = BENEFIT_TYPE_LABELS.get(p.get("benefit_type", "other"), "Other")
    status = STATUS_MAP.get(p.get("status", "unknown"), "Unknown")
    desc = p.get("description_plain_english") or ""

    eligibility = p.get("eligibility") or {}
    raw_eligibility = eligibility.get("raw_text", "") if isinstance(eligibility, dict) else ""

    content = desc
    if raw_eligibility:
        content += f"\n\nEligibility: {raw_eligibility}"
    if p.get("funding_amount"):
        content += f"\n\nFunding: {p['funding_amount']}"

    # Determine which profile labels apply to this program.
    # Search the full text (name + description + eligibility) for keywords so
    # programs are surfaced even when the pre-computed boolean flag isn't set.
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
            if profile_flags.get(flag) and any(kw in full_text for kw in keywords):
                targeted_labels.append(_LABEL_MAP[flag])

    # Compute funding % vs average
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
        "id":                str(p.get("_id", "")),
        "title":             p.get("name", ""),
        "summary":           desc,
        "content":           content,
        "category":          benefit_label,
        "department":        "San Jose City Council",
        "date":              _parse_date(p.get("date_created")).strftime("%Y-%m-%d") if _parse_date(p.get("date_created")) != datetime.min else (p.get("date_created") or ""),
        "status":            status,
        "priority":          "High" if p.get("status") == "approved" else "Medium",
        "tags":              [benefit_label, "San Jose", "Housing"],
        "apply_url":         p.get("apply_url"),
        "effective_date":    p.get("effective_date"),
        "closing_date":      p.get("closing_date"),
        "source_url":        p.get("source_url"),
        "funding_amount":    p.get("funding_amount"),
        "funding_pct_diff":  funding_pct_diff,
        "benefit_type":      p.get("benefit_type", "other"),
        "targeted_labels":   targeted_labels,
    }


@api_bp.route("/policies", methods=["GET"])
def get_policies():
    """Return housing programs from MongoDB, filtered by query params."""
    benefit_types = request.args.getlist("benefit_type") or None
    veteran_only = request.args.get("veteran_only") == "true"
    senior_only = request.args.get("senior_only") == "true"
    disability_preferred = request.args.get("disability_preferred") == "true"
    currently_homeless_only = request.args.get("currently_homeless_only") == "true"
    max_income = request.args.get("max_income", type=float)
    household_size = request.args.get("household_size", type=int)

    profile_flags = {
        "veteran_only": veteran_only,
        "senior_only": senior_only,
        "disability_preferred": disability_preferred,
        "currently_homeless_only": currently_homeless_only,
    }
    any_profile_selected = any(profile_flags.values())

    programs = search_programs(
        cities=["San Jose"],
        benefit_types=benefit_types,
        max_income=max_income,
        household_size=household_size,
    )

    # If the user has told us something about themselves, hide programs that are
    # exclusively for groups they're not part of.
    # e.g. a veteran who didn't check "disability" should not see disability-only programs.
    if any_profile_selected:
        def is_eligible(p):
            eligibility = p.get("eligibility") or {}
            for flag in profile_flags:
                if eligibility.get(flag) and not profile_flags[flag]:
                    return False
            return True
        programs = [p for p in programs if is_eligible(p)]

    programs = [p for p in programs if _is_user_facing(p)]
    programs = _dedup_programs(programs)
    avg_funding = compute_avg_funding(programs)
    return jsonify([transform(p, profile_flags, avg_funding) for p in programs]), 200


@api_bp.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy"}), 200


# ── Saved policies ──────────────────────────────────────────────────────────

@api_bp.route("/saves", methods=["GET"])
def get_saves():
    uid, err = _get_uid()
    if err:
        return err
    col = get_db()["saved_policies"]
    docs = col.find({"user_id": uid}, {"policy_id": 1, "_id": 0})
    return jsonify([d["policy_id"] for d in docs]), 200


@api_bp.route("/saves", methods=["POST"])
def add_save():
    uid, err = _get_uid()
    if err:
        return err
    policy_id = (request.get_json() or {}).get("policy_id")
    if not policy_id:
        return jsonify({"error": "policy_id required"}), 400
    col = get_db()["saved_policies"]
    col.update_one(
        {"user_id": uid, "policy_id": policy_id},
        {"$setOnInsert": {"saved_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return jsonify({"saved": True}), 200


@api_bp.route("/saves/<policy_id>", methods=["DELETE"])
def remove_save(policy_id):
    uid, err = _get_uid()
    if err:
        return err
    get_db()["saved_policies"].delete_one({"user_id": uid, "policy_id": policy_id})
    return jsonify({"saved": False}), 200


# ── Email notification subscriptions ─────────────────────────────────────────

@api_bp.route("/subscriptions", methods=["GET"])
def get_subscriptions():
    uid, err = _get_uid()
    if err:
        return err
    col = get_db()["subscriptions"]
    docs = col.find({"user_id": uid}, {"policy_id": 1, "_id": 0})
    return jsonify([d["policy_id"] for d in docs]), 200


@api_bp.route("/subscriptions", methods=["POST"])
def add_subscription():
    uid, err = _get_uid()
    if err:
        return err
    policy_id = (request.get_json() or {}).get("policy_id")
    if not policy_id:
        return jsonify({"error": "policy_id required"}), 400
    # Fetch the user's email from Firebase to store with the subscription
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
    uid, err = _get_uid()
    if err:
        return err
    get_db()["subscriptions"].delete_one({"user_id": uid, "policy_id": policy_id})
    return jsonify({"subscribed": False}), 200
