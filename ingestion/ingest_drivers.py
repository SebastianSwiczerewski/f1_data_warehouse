from config.database import get_db_cursor
from ingestion.api import fetch_paginated
from ingestion.logger import setup_logger

logger = setup_logger("ingest_drivers")


def fetch_all_drivers():
    logger.debug("Fetching drivers from API")
    drivers = fetch_paginated(
        endpoint="/drivers.json",
        data_path=["MRData", "DriverTable", "Drivers"]
    )
    logger.debug(f"Fetched {len(drivers)} drivers")
    return drivers


def create_table(cur):
    logger.debug("Ensuring drivers_raw table exists")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS drivers_raw (
            driver_id TEXT PRIMARY KEY,
            code TEXT,
            given_name TEXT,
            family_name TEXT,
            nationality TEXT,
            dob DATE
        );
    """)


def insert_drivers(cur, drivers):
    logger.debug("Inserting drivers into database")
    for d in drivers:
        cur.execute("""
            INSERT INTO drivers_raw
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (driver_id) DO NOTHING;
        """, (
            d["driverId"],
            d.get("code"),
            d.get("givenName"),
            d.get("familyName"),
            d.get("nationality"),
            d.get("dateOfBirth")
        ))
    logger.debug("Driver insert completed")


def main():
    logger.info("Starting drivers ingestion")

    conn, cur = get_db_cursor()

    try:
        drivers = fetch_all_drivers()
        create_table(cur)
        insert_drivers(cur, drivers)
        conn.commit()

        logger.info(f"Loaded {len(drivers)} drivers successfully")

    except Exception as e:
        conn.rollback()
        logger.exception("Fatal error during drivers ingestion")
        raise

    finally:
        cur.close()
        conn.close()
        logger.info("Drivers ingestion finished")


if __name__ == "__main__":
    main()