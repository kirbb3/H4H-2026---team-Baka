import re
from flask import Blueprint, jsonify, request
from src.data.database.db_connect import search_programs

api_bp = Blueprint("api", __name__, url_prefix="/api")

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

    # Determine which profile labels apply to this program
    targeted_labels = []
    if profile_flags and isinstance(eligibility, dict):
        for flag, label in PROFILE_FLAG_LABELS.items():
            if profile_flags.get(flag) and eligibility.get(flag):
                targeted_labels.append(label)

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
        "date":              p.get("date_created", ""),
        "status":            status,
        "priority":          "high" if p.get("status") == "approved" else "medium",
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

    avg_funding = compute_avg_funding(programs)
    return jsonify([transform(p, profile_flags, avg_funding) for p in programs]), 200


@api_bp.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy"}), 200
