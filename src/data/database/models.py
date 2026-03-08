"""
Data models / schema definitions for Housing Aid Navigator.

These are plain Python dicts/dataclasses — no ORM needed with pymongo.
Use these as the canonical shape for every document stored in MongoDB.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class EligibilityCriteria:
    location_states: list[str] = field(default_factory=list)   # e.g. ["CA", "TX"]
    location_cities: list[str] = field(default_factory=list)   # e.g. ["Austin", "Houston"]
    income_limit_annual: Optional[float] = None                 # USD
    household_size_max: Optional[int] = None
    citizenship_required: bool = False
    veteran_only: bool = False
    disability_preferred: bool = False
    senior_only: bool = False                                    # 62+
    currently_homeless_only: bool = False
    other_notes: str = ""


@dataclass
class Program:
    name: str
    agency: str
    benefit_type: str                        # "rent", "mortgage", "utility", "repair", "voucher"
    description_plain_english: str
    eligibility: EligibilityCriteria
    application_url: str
    documents_needed: list[str] = field(default_factory=list)
    processing_time_days: Optional[int] = None                  # estimated business days
    benefit_amount_max: Optional[float] = None                  # USD, None = varies
    match_score: float = 0.0                                    # set at query time, not stored
    slug: str = ""                                              # url-safe identifier

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("match_score", None)   # never persist computed field
        return d

    @staticmethod
    def from_dict(data: dict) -> "Program":
        eligibility_data = data.pop("eligibility", {})
        eligibility = EligibilityCriteria(**{
            k: v for k, v in eligibility_data.items()
            if k in EligibilityCriteria.__dataclass_fields__
        })
        return Program(
            eligibility=eligibility,
            **{k: v for k, v in data.items()
               if k in Program.__dataclass_fields__ and k != "eligibility"}
        )


# Benefit type labels shown in the UI
BENEFIT_TYPE_LABELS = {
    "rent":     "Rental Assistance",
    "mortgage": "Homebuyer / Mortgage Help",
    "utility":  "Utility Assistance",
    "repair":   "Home Repair",
    "voucher":  "Housing Voucher",
    "other":    "Other",
}
