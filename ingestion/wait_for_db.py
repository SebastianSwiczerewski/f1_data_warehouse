import time
import logging
import psycopg2

from config.database import get_db_connection

LOG = logging.getLogger("wait_for_db")


def main():
    LOG.info("Waiting for Postgres...")

    while True:
        try:
            conn = get_db_connection()
            conn.close()

            LOG.info("Postgres is ready!")
            break

        except psycopg2.OperationalError:
            LOG.info("Postgres not ready yet, retrying...")
            time.sleep(2)