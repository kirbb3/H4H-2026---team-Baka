import os
from pymongo import MongoClient, ASCENDING, TEXT
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from dotenv import load_dotenv

# Load environment variables from .env file (MONGO_URI, MONGO_DB_NAME)
load_dotenv()

# Module-level singleton — shared across all callers in the same process
_client: MongoClient | None = None

# Read connection settings from environment; fall back to defaults
MONGO_URI = os.getenv("MONGO_URI", "")
DB_NAME = os.getenv("MONGO_DB_NAME", "H4HDB1")
PROGRAMS_COLLECTION = "programs"


def get_client() -> MongoClient:
    """Return the shared MongoClient, creating it on first call."""
    global _client
    if _client is None:
        if not MONGO_URI:
            raise ValueError("MONGO_URI environment variable is not set.")
        # 5-second timeout so bad connections fail fast instead of hanging
        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return _client


def get_db() -> Database:
    """Return the H4HDB1 database handle."""
    return get_client()[DB_NAME]


def get_programs_collection() -> Collection:
    """Return the 'programs' collection where housing program docs are stored."""
    return get_db()[PROGRAMS_COLLECTION]


def ping() -> bool:
    """Check that the database is reachable. Returns True on success."""
    try:
        get_client().admin.command("ping")
        return True
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        print(f"[db_connect] MongoDB connection failed: {e}")
        print("  - Check that MONGO_URI is set correctly in your .env file.")
        print("  - Verify your IP is whitelisted in MongoDB Atlas.")
        return False


def ensure_indexes() -> None:
    """Create indexes on the programs collection for efficient querying.

    Call this once at app startup. Indexes are idempotent — safe to re-run.
    """
    col = get_programs_collection()

    # Unique index on slug so each program URL identifier is distinct
    col.create_index([("slug", ASCENDING)], unique=True, name="slug_unique")

    # Support filtering by state/city eligibility
    col.create_index(
        [("eligibility.location_states", ASCENDING)],
        name="location_states",
    )
    col.create_index(
        [("eligibility.location_cities", ASCENDING)],
        name="location_cities",
    )

    # Support filtering by program type (rent, mortgage, voucher, etc.)
    col.create_index([("benefit_type", ASCENDING)], name="benefit_type")

    # Support filtering by status (approved, proposed, open, closed, denied)
    col.create_index([("status", ASCENDING)], name="status")

    # Support filtering by effective date
    col.create_index([("effective_date", ASCENDING)], name="effective_date")

    # Full-text index lets users search by keyword across name and description
    col.create_index(
        [("name", TEXT), ("description_plain_english", TEXT)],
        name="text_search",
    )


# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------

def insert_program(program_doc: dict) -> str:
    """Insert a new program document. Returns the inserted document's ID."""
    result = get_programs_collection().insert_one(program_doc)
    return str(result.inserted_id)


def upsert_program(program_doc: dict) -> None:
    """Insert or update a program matched by its slug.

    Used by the scraper/processor so re-running a scrape won't create duplicates.
    """
    col = get_programs_collection()
    col.update_one(
        {"slug": program_doc["slug"]},   # match on unique slug
        {"$set": program_doc},           # overwrite all fields with fresh data
        upsert=True,                     # create the doc if it doesn't exist yet
    )


def get_program_by_slug(slug: str) -> dict | None:
    """Fetch a single program by its URL-safe slug. Returns None if not found."""
    return get_programs_collection().find_one({"slug": slug}, {"_id": 0})


def get_all_programs(query: dict | None = None) -> list[dict]:
    """Return all programs, optionally filtered by a raw MongoDB query dict."""
    return list(get_programs_collection().find(query or {}, {"_id": 0}))


def search_programs(
    states: list[str] | None = None,
    cities: list[str] | None = None,
    benefit_types: list[str] | None = None,
    max_income: float | None = None,
    household_size: int | None = None,
    veteran_only: bool = False,
    senior_only: bool = False,
    disability_preferred: bool = False,
    currently_homeless_only: bool = False,
    text_query: str | None = None,
    exclude_denied: bool = True,
) -> list[dict]:
    """Search programs using the user's eligibility criteria.

    All filters are optional and additive (AND logic). Only programs that
    satisfy every provided filter are returned.
    """
    query: dict = {}

    # Exclude denied programs by default — users only want actionable results
    if exclude_denied:
        query["status"] = {"$ne": "denied"}

    # Location filters — program must serve at least one of the given states/cities
    if states:
        query["eligibility.location_states"] = {"$in": states}
    if cities:
        query["eligibility.location_cities"] = {"$in": cities}

    # Program category filter (e.g. "rent", "mortgage", "voucher")
    if benefit_types:
        query["benefit_type"] = {"$in": benefit_types}

    # Include programs whose income limit is at or above the user's income,
    # or programs with no income limit set (None means no restriction)
    if max_income is not None:
        query.setdefault("$and", []).append({"$or": [
            {"eligibility.income_limit_annual": {"$gte": max_income}},
            {"eligibility.income_limit_annual": None},
        ]})

    # Include programs that support the given household size or have no cap
    if household_size is not None:
        query.setdefault("$and", []).append({"$or": [
            {"eligibility.household_size_max": {"$gte": household_size}},
            {"eligibility.household_size_max": None},
        ]})

    # Boolean eligibility flags — only filter when the user asserts the flag
    if veteran_only:
        query["eligibility.veteran_only"] = True
    if senior_only:
        query["eligibility.senior_only"] = True
    if disability_preferred:
        query["eligibility.disability_preferred"] = True
    if currently_homeless_only:
        query["eligibility.currently_homeless_only"] = True

    # Full-text keyword search across name and description fields
    if text_query:
        query["$text"] = {"$search": text_query}

    return list(get_programs_collection().find(query))


def delete_program(slug: str) -> bool:
    """Delete a program by slug. Returns True if a document was removed."""
    result = get_programs_collection().delete_one({"slug": slug})
    return result.deleted_count > 0


def close_connection() -> None:
    """Close the MongoDB connection and reset the singleton.

    Call this on app shutdown to cleanly release the connection pool.
    """
    global _client
    if _client is not None:
        _client.close()
        _client = None
