from pathlib import Path
import logging
import json
import sys

from ingestion.wait_for_db import main as wait_for_db
from ingestion.ingest_drivers import main as ingest_drivers
from ingestion.ingest_constructors import main as ingest_constructors
from ingestion.ingest_races import main as ingest_races
from ingestion.ingest_results import main as ingest_results

LOG = logging.getLogger("ingest_all")

# shared progress file (mounted to host)
PROGRESS_FILE = Path("/app/ingestion/logs/ingestion_progress.json")


def update_stage(stage_name):
    """
    Publish current ingestion stage to shared progress file.
    """
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)

    PROGRESS_FILE.write_text(
        json.dumps({
            "stage": stage_name,
            "status": "running"
        })
    )


def main():
    LOG.info("Starting full ingestion pipeline")

    steps = [
        ("wait_for_db", wait_for_db),
        ("drivers", ingest_drivers),
        ("constructors", ingest_constructors),
        ("races", ingest_races),
        ("results", ingest_results),
    ]

    for name, step in steps:
        try:
            update_stage(name)
            LOG.info(f"Running step: {name}")
            step()
            LOG.info(f"Finished step: {name}")

        except SystemExit as e:
            LOG.error(f"Pipeline failed during stage: {name}")

            PROGRESS_FILE.write_text(
                json.dumps({
                    "stage": name,
                    "status": "failed",
                    "exit_code": e.code
                })
            )

            sys.exit(e.code)

        except Exception:
            LOG.exception(f"Unexpected failure in stage: {name}")

            PROGRESS_FILE.write_text(
                json.dumps({
                    "stage": name,
                    "status": "failed",
                    "exit_code": 1
                })
            )

            sys.exit(1)

    PROGRESS_FILE.write_text(
        json.dumps({
            "stage": "completed",
            "status": "success"
        })
    )

    Path("/tmp/INGESTION_DONE").touch()
    LOG.info("Ingestion completed successfully.")
    

if __name__ == "__main__":
    main()