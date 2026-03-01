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


def transform(p):
    benefit_label = BENEFIT_TYPE_LABELS.get(p.get("benefit_type", "other"), "Other")
    status = STATUS_MAP.get(p.get("status", "unknown"), "Unknown")
    desc = p.get("description_plain_english") or ""

    raw_eligibility = ""
    if isinstance(p.get("eligibility"), dict):
        raw_eligibility = p["eligibility"].get("raw_text") or ""

    content = desc
    if raw_eligibility:
        content += f"\n\nEligibility: {raw_eligibility}"
    if p.get("funding_amount"):
        content += f"\n\nFunding: {p['funding_amount']}"

    return {
        "id":             str(p.get("_id", "")),
        "title":          p.get("name", ""),
        "summary":        desc,
        "content":        content,
        "category":       benefit_label,
        "department":     "San Jose City Council",
        "date":           p.get("date_created", ""),
        "status":         status,
        "priority":       "high" if p.get("status") == "approved" else "medium",
        "tags":           [benefit_label, "San Jose", "Housing"],
        "apply_url":      p.get("apply_url"),
        "effective_date": p.get("effective_date"),
        "closing_date":   p.get("closing_date"),
        "source_url":     p.get("source_url"),
        "funding_amount": p.get("funding_amount"),
        "benefit_type":   p.get("benefit_type", "other"),
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

    programs = search_programs(
        cities=["San Jose"],
        benefit_types=benefit_types,
        veteran_only=veteran_only,
        senior_only=senior_only,
        disability_preferred=disability_preferred,
        currently_homeless_only=currently_homeless_only,
        max_income=max_income,
        household_size=household_size,
    )
    return jsonify([transform(p) for p in programs]), 200


@api_bp.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy"}), 200
