# 🏎️ Formula 1 Data Warehouse

An end-to-end data engineering project that ingests, models, and transforms historical Formula 1 data into an analytics-ready warehouse.

The project demonstrates modern data engineering and analytics engineering best practices, including robust ingestion, layered transformations, data quality testing, and star-schema modeling.

---

## Overview
This warehouse enables analysis of Formula 1 history such as:
- Driver career performance
- Constructor dominance by season
- Race and calendar analytics

The pipeline is designed to be **idempotent, resumable, and analytics-ready**, closely mirroring real-world production patterns.

---

## Tech Stack
- **Python** – API ingestion & orchestration
- **PostgreSQL** – relational warehouse (Dockerized)
- **Docker & Docker Compose** – local infrastructure
- **dbt** – transformations, testing, and modeling
- **SQL** – analytics & data modeling
- **Public Ergast API** (via `api.jolpi.ca` mirror)

---

## Architecture

### Ingestion
- Python ingestion scripts pull data from the Ergast F1 API
- Explicit handling of:
  - API pagination
  - Rate limits
  - Seasonal batch ingestion
- Pipelines are **idempotent** and safe to re-run

### Storage
- PostgreSQL running locally in Docker
- Schema-based separation:
  - `public` → raw ingested tables
  - `staging` → dbt staging views
  - `analytics` → analytics-ready marts

### Transformation
- dbt used to implement a layered transformation approach:
  - **Raw → Staging → Marts**
- Data quality enforced via dbt tests
- Star schema modeled for analytics consumption

### Orchestration
- Docker Compose orchestrates the full pipeline:
  - PostgreSQL initializes the warehouse
  - Ingestion container loads raw data
  - dbt container builds staging and analytics models
- dbt execution is automatically triggered after ingestion completes

---

## Data Model

### Raw Tables
- `drivers_raw`
- `constructors_raw`
- `races_raw`
- `results_raw`

### Staging Models (dbt)
- `stg_drivers`
- `stg_constructors`
- `stg_races`
- `stg_results`

### Analytics Marts
**Dimensions**
- `dim_drivers`
- `dim_constructors`
- `dim_races`

**Fact**
- `fact_results`  
  *(one row per driver per race)*

---

## Data Quality & Testing
- dbt tests implemented for:
  - `not_null`
  - `unique`
  - `relationships` (foreign key integrity)
- Ensures referential integrity between facts and dimensions

---

## Warehouse Schema

![Warehouse Schema](docs/lineage.png)

---

## Example Analytics
Example SQL analytics queries are available in `f1_dbt/analyses/`, including:
- Top drivers by career points
- Constructor dominance by season
- Driver win counts
- Race distribution by country

---
## Architecture Overview

This project demonstrates a production-style, containerized ELT architecture with an automated BI layer, reproducible across environments via Docker Compose.

The stack includes:

- **PostgreSQL** → Data warehouse  
- **Python ingestion service** → Historical Formula 1 data ingestion  
- **dbt** → Data transformation and validation  
- **Metabase** → Business intelligence and dashboards  

All services are executed and coordinated through a single Docker Compose workflow, enabling fully automated and reproducible infrastructure provisioning, data ingestion, transformation, and dashboard restoration.

---
## How to Run Locally

### Prerequisites

Before running the project locally, ensure you have the following installed:

- **Git**
- **Docker & Docker Compose**
  - https://docs.docker.com/get-docker/


### ⏱️ Execution Time

Execution time depends primarily on API rate limits during ingestion.

Typical runtimes:
- **Full historical ingestion**: ~25–30 minutes  
  (~28,000 race result records)
- **dbt transformations & tests**: < 1 minute

The pipeline is idempotent and safe to re-run. Subsequent runs may complete faster if data already exists.

### 💾 Local Resource Usage (Approximate)

Docker resources used by the pipeline (measured on a clean run):

#### Docker Images

- **metabase/metabase:latest** → 1.56 GB  
- **docker-ingestion** → 881 MB  
- **dbt-postgres (1.9.latest)** → 883 MB  
- **postgres:18** → 671 MB  

> Total image footprint: ~4.0 GB

#### Persistent Data (Docker Volumes)

- **PostgreSQL warehouse data** → ~103 MB  
- **Metabase application data** → grows over time (initial seed: ~0 MB)  
- **Ingestion state volume** → negligible  

> Total persistent warehouse footprint after full ingestion: ~100 MB

#### Runtime Memory Usage (Idle State)

- **Metabase** → ~1.0 GB RAM  
- **PostgreSQL** → ~80 MB RAM  
- Other services run briefly during ingestion & transformation.

#### Docker Build Cache

- ~950 MB (can be safely pruned if needed)

---

*These resources are typical for a fully containerized local analytics stack and can be completely removed using:*

```bash
docker compose down -v
```

### 1️⃣ Local Environment Setup

  Clone the repository

  ```bash
  git clone https://github.com/SebastianSwiczerewski/f1_data_warehouse.git
  cd f1_data_warehouse/
  ```

  Create a local .env file from the example provided. No edits required for local runs.

  ```bash
  cp .env.example .env
  ```

### 2️⃣ Run the Entire Pipeline
  The entire data pipeline is orchestrated through Docker Compose and can be executed with a **single command**.

  ```bash
  cd docker/
  docker compose --env-file ../.env up --build
  ```

  This command is the **core entry point** of the project. It provisions infrastructure, ingests data, and builds analytics models, starts the BI layer, and restores dashboards - fully automated and end-to-end.

  The system is ready once the terminal displays:

  ```bash
  🚀 F1 DATA WAREHOUSE IS READY 🚀
  ```

Under the hood, it performs the following steps:

1. **Provision the Warehouse**
   - Starts a PostgreSQL container
   - Initializes schemas and persistent storage
   - Creates the Metabase application database

2. **Ingest Raw Formula 1 Data**
   - Executes Python ingestion pipelines
   - Pulls historical data from the Ergast API
   - Handles pagination, retries, and API rate limits
   - Loads data into raw tables in the `public` schema

3. **Transform & Validate Data with dbt**
   - Builds staging models as views (`dbt_staging`)
   - Builds analytics-ready marts as tables (`dbt_analytics`)
   - Executes data quality tests:
     - `not null`
     - `unique`
     - `relationships`

4. **Start Metabase (BI Layer)**
   - Launches Metabase as a containerized service
   - Connects it automatically to the warehouse
   - Configues the application database

5. **Automatically Restore Pre-Built Dashboards**
   - Restores a pre-configured Metabase environment from a version-controlled database seed 
   - Restores:
     - F1 Season Performance
     - F1 Long-Term Insights
   - Applies all saved filters, formatting and visual styling (no manual dashboard setup required)
    

Once this step completes successfully, the warehouse and BI layer are **fully analytics-ready**.

### 3️⃣ Access the Dashboards

Once the pipeline completes, open in a web browser:

```bash
http://localhost:3000
```
The Metabase instance is automatically provisioned and restored from a version-controlled seed file, ensuring identical dashboards across environments without any manual configuration.

Login with

```bash
Email: f1@metabase.com  
Password: Alonso1
```

Navigate to:

```bash
Our Analytics → F1 Dashboards
```
You will find:

- **F1 Long-Term Insights**
- **F1 Season Performance**

All dashboards are fully configured, including:

- Saved questions  
- Filters  
- Formatting  
- Visual styling  
- Data model mappings  

No manual setup is required.

### 4️⃣ Validate the Warehouse (Optional)

  ```bash
  cd docker/
  docker exec -it f1_postgres psql -U f1_user -d f1_raw
  ```
  
  List schemas:

  ```bash
  \dn                
  ```
  You should see the following schemas:

  - **public** → raw tables  
  - **dbt_staging** → staging views  
  - **dbt_analytics** → dimension & fact tables

  ```bash
  \dt public.*          # List of raw tables
  \dv dbt_staging.*     # List of staging views
  \dt dbt_analytics.*   # List of dimension & fact tables
  ```


  Other useful commands

  ```bash
  \dt                 # List tables
  \dv                 # List views
  \d table_name       # Describe table
  \q                  # Exit
  ```

  For example analytics queries using fact and dimension models check ./f1_dbt/analyses/f1_analytics.sql


### 5️⃣ Tear Down Local Environment

  Stop Docker services (keep data)

  ```bash
  docker compose down
  ```

  ⚠️ WARNING: This deletes data

  ```bash
  docker compose down -v
  ```


## Pipeline Summary

This project demonstrates a production-style ELT + BI architecture where:
- Infrastructure is fully containerized (PostgreSQL, ingestion, dbt, Metabase)
- Ingestion and transformation are decoupled
- dbt enforces modeling standards and data quality
- Analytics marts are built using dimensional modeling principles
- The BI layer is automatically provisioned and restored

The Metabase container automatically restores a pre-configured BI environment from a version-controlled SQL seed file (metabase_seed.sql), ensuring identical dashboards across environments.

Running a single command:

```bash
docker compose --env-file ../.env up --build
```

provisions infrastructure, ingests historical F1 data, builds analytics models, and launches fully configured dashboards — end-to-end and reproducibly.