# API Config

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

F1_API_BASE_URL = os.getenv(
    "F1_API_BASE_URL",
    "https://api.jolpi.ca/ergast/f1"
)

HEADERS = {
    "User-Agent": "F1DataEngineering/1.0",
    "Accept": "application/json"
}

MAX_REQUESTS_PER_SECOND = 4
MIN_REQUEST_INTERVAL = 1 / MAX_REQUESTS_PER_SECOND
HARD_RATE_LIMIT_SLEEP = 60


class RateLimitExceeded(Exception):
    """Raised when API rate limit is hit and ingestion should pause."""


def fetch_paginated(endpoint: str, data_path: list):
    limit = 100
    offset = 0
    results = []
    last_request_time = 0

    while True:
        elapsed = time.time() - last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)

        url = f"{F1_API_BASE_URL}{endpoint}"

        response = requests.get(
            url,
            headers=HEADERS,
            params={"limit": limit, "offset": offset}
        )

        last_request_time = time.time()

        if response.status_code == 429:
            raise RateLimitExceeded(
                "API rate limit exceeded (HTTP 429)"
            )

        if response.status_code in {500, 502, 503, 504}:
            raise RateLimitExceeded(
                f"Server error {response.status_code}"
            )

        response.raise_for_status()

        data = response.json()
        batch = data

    
        for key in data_path:
            if isinstance(batch, dict):
                batch = batch.get(key)
            else:
                batch = None
                break

        if not isinstance(batch, list):
            raise ValueError(f"Unexpected API structure at {endpoint}: {batch}")

        if not batch:
            break

        results.extend(batch)
        offset += limit

    return results