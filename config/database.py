import os
import psycopg2
from dotenv import load_dotenv
from pathlib import Path

# Load root .env
env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path)


def get_db_connection():
    host = os.getenv("POSTGRES_HOST", "postgres")

    # outside Docker (CLI) - use localhost
    if os.getenv("RUNNING_IN_DOCKER") != "true":
        host = "localhost"

    return psycopg2.connect(
        host=host,
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "f1_raw"),
        user=os.getenv("POSTGRES_USER", "f1_user"),
        password=os.getenv("POSTGRES_PASSWORD", "f1_password"),
    )

# reusable DB configs with psycopg2.connect(**get_db_params())

def get_db_params():
    return {
        "host": os.getenv("POSTGRES_HOST"),
        "port": os.getenv("POSTGRES_PORT"),
        "dbname": os.getenv("POSTGRES_DB"),
        "user": os.getenv("POSTGRES_USER"),
        "password": os.getenv("POSTGRES_PASSWORD"),
    }

def get_db_cursor():
    conn = get_db_connection()
    return conn, conn.cursor()