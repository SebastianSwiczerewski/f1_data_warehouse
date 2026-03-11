import os
import time
import json
import sys
from pathlib import Path

from config.database import get_db_cursor
from ingestion.api import fetch_paginated, RateLimitExceeded
from ingestion.logger import setup_logger

logger = setup_logger("ingest_results")

START_SEASON = int(os.getenv("START_SEASON", 1950))
END_SEASON = int(os.getenv("END_SEASON", 2025))

MAX_RETRIES_PER_SEASON = 3


def fetch_results_for_season(season):
    logger.debug(f"Fetching results for season {season}")
    return fetch_paginated(
        endpoint=f"/{season}/results.json",
        data_path=["MRData", "RaceTable", "Races"]
    )


def ingest_season(cur, season):
    races = fetch_results_for_season(season)
    inserted = 0

    for race in races:
        round_ = race["round"]
        race_id = f"{season}_{round_}"

        for res in race["Results"]:
            cur.execute("""
                INSERT INTO results_raw
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (race_id, driver_id) DO NOTHING;
            """, (
                race_id,
                int(season),
                int(round_),
                res["Driver"]["driverId"],
                res["Constructor"]["constructorId"],
                int(res["position"]),
                float(res["points"]),
                res.get("status")
            ))
            inserted += 1

    return inserted


def create_table(cur):
    logger.debug("Ensuring results_raw table exists")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS results_raw (
            race_id TEXT,
            season INT,
            round INT,
            driver_id TEXT,
            constructor_id TEXT,
            position INT,
            points FLOAT,
            status TEXT,
            PRIMARY KEY (race_id, driver_id)
        );
    """)


def main():
    logger.info("Starting historical results ingestion")

    PROGRESS_FILE = Path("/app/ingestion/logs/ingestion_progress.json")

    conn, cur = get_db_cursor()

    def publish_progress(
        season_index,
        total_seasons,
        total_inserted,
        status="running",
        retry=None,
        sleep_seconds=None,
    ):
        estimated_laps = total_inserted * 60
        estimated_distance_km = estimated_laps * 5

        data = {
            "stage": "results",
            "season_index": season_index,
            "total_seasons": total_seasons,
            "total_inserted": total_inserted,
            "estimated_laps": estimated_laps,
            "estimated_distance_km": estimated_distance_km,
            "status": status,
        }

        if retry is not None:
            data["retry"] = retry

        if sleep_seconds is not None:
            data["sleep_seconds"] = sleep_seconds

        PROGRESS_FILE.write_text(json.dumps(data))

    try:
        create_table(cur)

        total_inserted = 0
        seasons = list(range(START_SEASON, END_SEASON + 1))
        total_seasons = len(seasons)

        for idx, season in enumerate(seasons, start=1):
            retries = 0

            while True:
                try:
                    inserted = ingest_season(cur, season)
                    conn.commit()

                    total_inserted += inserted

                    publish_progress(
                        season_index=idx,
                        total_seasons=total_seasons,
                        total_inserted=total_inserted,
                        status="running",
                    )

                    break

                except RateLimitExceeded as e:
                    retries += 1
                    logger.warning(f"Season {season}: {str(e)}")

                    if retries >= MAX_RETRIES_PER_SEASON:
                        logger.error(
                            f"Season {season} exceeded max retries."
                        )
                        conn.rollback()
                        sys.exit(2)

                    sleep_time = 180 + (60 * (retries - 1))
                    sleep_time = min(sleep_time, 300)

                    publish_progress(
                        season_index=idx,
                        total_seasons=total_seasons,
                        total_inserted=total_inserted,
                        status="cooldown",
                        retry=retries,
                        sleep_seconds=sleep_time,
                    )

                    logger.info(
                        f"Cooling down {sleep_time}s (retry {retries})"
                    )

                    for remaining in range(sleep_time, 0, -1):

                        publish_progress(
                            season_index=idx,
                            total_seasons=total_seasons,
                            total_inserted=total_inserted,
                            status="cooldown",
                            retry=retries,
                            sleep_seconds=remaining,
                        )

                        time.sleep(1)

                    continue

                except Exception:
                    logger.exception(
                        f"Fatal error while ingesting season {season}"
                    )
                    conn.rollback()
                    sys.exit(1)

        logger.info(
            f"Ingestion finished successfully. "
            f"Total results processed: {total_inserted}"
        )

    finally:
        cur.close()
        conn.close()
        logger.info("Database connection closed")