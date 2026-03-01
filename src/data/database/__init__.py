from src.data.database.db_connect import (
    ping,
    ensure_indexes,
    insert_program,
    upsert_program,
    get_program_by_slug,
    get_all_programs,
    search_programs,
    delete_program,
    close_connection,
)

if __name__ == "__main__":
    # --- ping ---
    # Check if the database is reachable
    is_connected = ping()
    print("Connected:", is_connected)  # True or False

    # --- ensure_indexes ---
    # Run once at startup to create indexes for fast querying
    ensure_indexes()

    # --- insert_program ---
    # Add a brand-new program document; fails if slug already exists
    new_id = insert_program({
        "slug": "ca-section-8",
        "name": "California Section 8",
        "description_plain_english": "Federal voucher program for low-income renters.",
        "benefit_type": "voucher",
        "eligibility": {
            "location_states": ["CA"],
            "location_cities": [],
            "income_limit_annual": 40000,
            "household_size_max": 6,
            "veteran_only": False,
            "senior_only": False,
            "disability_preferred": False,
            "currently_homeless_only": False,
        },
    })
    print("Inserted ID:", new_id)

    # --- upsert_program ---
    # Insert or update a program matched by slug — safe to re-run
    upsert_program({
        "slug": "ca-section-8",
        "name": "California Section 8 (updated)",
        "description_plain_english": "Updated description.",
        "benefit_type": "voucher",
        "eligibility": {
            "location_states": ["CA"],
            "location_cities": ["Los Angeles"],
            "income_limit_annual": 45000,
            "household_size_max": 6,
            "veteran_only": False,
            "senior_only": False,
            "disability_preferred": False,
            "currently_homeless_only": False,
        },
    })
    print("Upserted ca-section-8")

    # --- get_program_by_slug ---
    # Fetch a single program by its slug; returns None if not found
    program = get_program_by_slug("ca-section-8")
    print("Fetched:", program)

    # --- get_all_programs ---
    # Return every program in the database
    all_programs = get_all_programs()
    print("Total programs:", len(all_programs))

    # --- get_all_programs with a raw query ---
    # Only fetch voucher programs
    vouchers = get_all_programs({"benefit_type": "voucher"})
    print("Voucher programs:", len(vouchers))

    # --- search_programs ---
    # Filter by any combination of eligibility criteria
    results = search_programs(
        states=["CA"],
        cities=["Los Angeles"],
        benefit_types=["voucher", "rent"],
        max_income=45000,
        household_size=3,
        text_query="low income housing",
    )
    print("Search results:", len(results))

    # --- delete_program ---
    # Remove a program by slug; returns True if something was deleted
    deleted = delete_program("ca-section-8")
    print("Deleted:", deleted)  # True

    # --- close_connection ---
    # Call this on app shutdown to cleanly release the connection pool
    close_connection()
    print("Done.")
