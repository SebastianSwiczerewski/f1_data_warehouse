from config.database import get_db_cursor
from ingestion.api import fetch_paginated
from ingestion.logger import setup_logger

logger = setup_logger("ingest_races")


def fetch_all_races():
    logger.debug("Fetching races from API")
    races = fetch_paginated(
        endpoint="/races.json",
        data_path=["MRData", "RaceTable", "Races"]
    )
    logger.debug(f"Fetched {len(races)} races")
    return races


def create_table(cur):
    logger.debug("Ensuring races_raw table exists")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS races_raw (
            race_id TEXT PRIMARY KEY,
            season INT,
            round INT,
            race_name TEXT,
            race_date DATE,
            race_time TIME,
            circuit_id TEXT,
            circuit_name TEXT,
            locality TEXT,
            country TEXT
        );
    """)


def insert_races(cur, races):
    logger.debug("Inserting races into database")
    for r in races:
        cur.execute("""
            INSERT INTO races_raw
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (race_id) DO NOTHING;
        """, (
            f"{r['season']}_{r['round']}",   # synthetic race_id
            int(r["season"]),
            int(r["round"]),
            r.get("raceName"),
            r.get("date"),
            r.get("time"),
            r["Circuit"]["circuitId"],
            r["Circuit"]["circuitName"],
            r["Circuit"]["Location"].get("locality"),
            r["Circuit"]["Location"].get("country")
        ))
    logger.debug("Race insert completed")


def main():
    logger.info("Starting races ingestion")

    conn, cur = get_db_cursor()

    try:
        races = fetch_all_races()
        create_table(cur)
        insert_races(cur, races)
        conn.commit()

        logger.info(f"Loaded {len(races)} races successfully")

    except Exception as e:
        conn.rollback()
        logger.exception("Fatal error during races ingestion")
        raise

    finally:
        cur.close()
        conn.close()
        logger.info("Races ingestion finished")


if __name__ == "__main__":
    main()