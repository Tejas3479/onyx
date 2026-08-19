"""Data seeder — loads seed data into the database at app startup."""

import logging

logger = logging.getLogger("onyx.data_seeder")


async def seed_database() -> dict[str, int]:
    """Seed all reference data into the database.

    Called during app startup. Safe to call multiple times —
    each seeder checks if data already exists before inserting.
    """
    from services.department_lpp import seed_department_records
    from services.gem_rate_lookup import seed_all

    results = await seed_all()
    dept_count = await seed_department_records()
    results["department_lpp"] = dept_count
    total = sum(results.values())
    if total > 0:
        logger.info(f"Database seeded: {results}")
    else:
        logger.debug("Database already seeded, no new data inserted")
    return results
