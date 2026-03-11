import os
import time
import subprocess
import json 
import shutil
from pathlib import Path

from rich.live import Live
from rich.table import Table
from rich.console import Console
from rich.spinner import Spinner
from rich.progress import Progress, BarColumn, TextColumn
from rich.panel import Panel

from config.database import get_db_cursor

console = Console()

# -----------------------------
# Docker Helpers
# -----------------------------

def docker_state(container):
    try:
        result = subprocess.check_output(
            ["docker", "inspect", "-f", "{{.State.Status}}", container],
            stderr=subprocess.DEVNULL,
        )
        return result.decode().strip()
    except:
        return "not_created"


def docker_health(container):
    try:
        result = subprocess.check_output(
            ["docker", "inspect", "-f", "{{.State.Health.Status}}", container],
            stderr=subprocess.DEVNULL,
        )
        return result.decode().strip()
    except:
        return "unknown"
    
def get_pipeline_stats():
    try:
        conn, cur = get_db_cursor()

        cur.execute("SELECT COUNT(*) FROM drivers_raw;")
        drivers = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM constructors_raw;")
        constructors = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM races_raw;")
        races = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM results_raw;")
        results = cur.fetchone()[0]

        cur.execute("SELECT COUNT(DISTINCT season) FROM races_raw;")
        seasons = cur.fetchone()[0]

        conn.close()

        return drivers, constructors, races, results, seasons

    except Exception as e:
        print("Pipeline summary DB error:", e)
        return None, None, None, None, None

def render_pipeline_summary(start_time):

    drivers, constructors, races, results, seasons = get_pipeline_stats()

    runtime = format_runtime(time.time() - start_time)

    drivers = drivers or 0
    constructors = constructors or 0
    races = races or 0
    results = results or 0
    seasons = seasons or "?"
    laps = int(results * 60)
    distance = int(laps * 5)

    table = Table(expand=True)

    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    table.add_row("Seasons processed", f"{seasons}")
    table.add_row("Grand Prix races", f"{races:,}")
    table.add_row("Driver results", f"{results:,}")
    table.add_row("Drivers ingested", f"{drivers:,}")
    table.add_row("Constructors", f"{constructors:,}")
    table.add_row("Laps estimated", f"~{laps:,}")
    table.add_row("Distance covered", f"~{distance:,} km")
    table.add_row("Total runtime", runtime)

    terminal_width = shutil.get_terminal_size().columns

    panel = Panel(
        table,
        title="🏁 F1 Pipeline Summary",
        border_style="bright_blue",
        width=min(terminal_width - 2, 120)
    )

    console.print(panel)

    console.print("\n[bold cyan]📊 Dashboard available at:[/bold cyan]")
    console.print("[blue]http://localhost:3000[/blue]\n")

# -----------------------------
# DB Polling (Live Ingestion %)
# -----------------------------

def get_ingestion_progress():
    path = Path("ingestion/logs/ingestion_progress.json")
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except:
        return None
    

def get_results_count():
    try:
        conn, cur = get_db_cursor()

        cur.execute("SELECT COUNT(*) FROM results_raw;")
        count = cur.fetchone()[0]
        conn.close()
        return count
    except:
        return 0
    
def format_runtime(seconds):
    minutes, sec = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)

    if hours > 0:
        return f"{hours}h {minutes}m {sec}s"
    elif minutes > 0:
        return f"{minutes}m {sec}s"
    else:
        return f"{sec}s"

# -----------------------------
# Dashboard Renderer
# -----------------------------

def render_dashboard(start_time):

    table = Table(expand=True)
    table.add_column("Step", justify="left")
    table.add_column("Status", justify="left")

    # postgreSQL
    pg_health = docker_health("f1_postgres")

    if pg_health == "healthy":
        pg_status = "[green]✓ Healthy[/green]"
    else:
        pg_status = Spinner("dots", text="[yellow]Starting...[/yellow]")

    table.add_row("[1/5] PostgreSQL", pg_status)

    # ingestion 
    progress_data = get_ingestion_progress()
    ingest_state = docker_state("f1_ingestion")

    if ingest_state == "exited":
        exit_code = docker_exit_code("f1_ingestion")

        if exit_code == "0":
            ingest_status = "[green]✓ Completed[/green]"
        elif exit_code == "2":
            ingest_status = "[red]❌ Failed (API limit)[/red]"
        else:
            ingest_status = "[red]❌ Failed[/red]"

        table.add_row("[2/5] Ingestion", ingest_status)

    elif progress_data:

        stage = progress_data.get("stage")

        if stage != "results":
            table.add_row(
                "[2/5] Ingestion",
                Spinner("dots", text=f"[yellow]{stage.capitalize()}...[/yellow]")
            )

        else:
            season = progress_data.get("season_index", 0)
            total_seasons = progress_data.get("total_seasons", 1)
            total_inserted = progress_data.get("total_inserted", 0)
            status = progress_data.get("status", "running")

            ratio = season / total_seasons
            percent = int(ratio * 100)

            progress_bar = Progress(
                TextColumn("[bold yellow]🏁 Historical Results"),
                BarColumn(
                    bar_width=55,
                    complete_style="bright_magenta",
                    finished_style="bright_magenta",
                    pulse_style="bright_magenta",
                ),
                TextColumn("[cyan]{task.percentage:>3.0f}%"),
                expand=True,
            )

            task = progress_bar.add_task(
                description="results",
                total=100,
                completed=percent,
            )

            table.add_row("[2/5] Ingestion", progress_bar)

            estimated_laps = progress_data.get("estimated_laps", 0)
            estimated_distance = progress_data.get("estimated_distance_km", 0)

            details = (
                f"Season:            {season} / {total_seasons}\n"
                f"Driver Results:    {total_inserted:,}\n"
                f"Laps:             ~{estimated_laps:,}\n"
                f"Distance:         ~{estimated_distance:,} km\n"
            )

            if status == "cooldown":
                retry = progress_data.get("retry")
                sleep = progress_data.get("sleep_seconds")
                details += "[red]⚠ API rate limit reached[/red]\n"
                details += f"[red]Cooling down {sleep}s[/red]"

            table.add_row("", details)

    else:
        table.add_row(
            "[2/5] Ingestion",
            Spinner("dots", text="[yellow]Pending...[/yellow]")
        )
    # dbt 
    dbt_state = docker_state("f1_dbt")
    ingestion_state = docker_state("f1_ingestion")

    if dbt_state == "exited":
        dbt_status = "[green]✓ Completed[/green]"

    elif dbt_state == "running" and ingestion_state != "exited":
        dbt_status = Spinner("dots", text="[yellow]Pending...[/yellow]")

    elif dbt_state == "running" and ingestion_state == "exited":
        dbt_status = Spinner("dots", text="[yellow]Running models...[/yellow]")

    else:
        dbt_status = Spinner("dots", text="[yellow]Pending...[/yellow]")

    table.add_row("[3/5] dbt Models", dbt_status)

    # metabase restore 
    restore_state = docker_state("f1_metabase_restore")

    if restore_state == "exited":
        restore_status = "[green]✓ Completed[/green]"
    elif restore_state == "running":
        restore_status = Spinner("dots", text="[yellow]Restoring...[/yellow]")
    else:
        restore_status = Spinner("dots", text="[yellow]Pending...[/yellow]")

    table.add_row("[4/5] Metabase Restore", restore_status)

    # dashboard 
    meta_health = docker_health("f1_metabase")

    if meta_health == "healthy":
        meta_status = "[green]✓ Healthy[/green]"
    else:
        meta_status = Spinner("dots", text="[yellow]Starting...[/yellow]")

    table.add_row("[5/5] Dashboard", meta_status)

    # elapsed time 
    elapsed = format_runtime(time.time() - start_time)
    table.add_row("[bold]Elapsed Time[/bold]", f"[cyan]{elapsed}[/cyan]")

    return Panel(table, title="🚀 F1 Data Warehouse Pipeline", border_style="bright_blue")



def docker_exit_code(container):
    try:
        return subprocess.check_output(
            ["docker", "inspect", "-f", "{{.State.ExitCode}}", container],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except:
        return None


def main():
    start_time = time.time()

    with Live(render_dashboard(start_time), refresh_per_second=4) as live:
        while True:
            live.update(render_dashboard(start_time))

            ingestion_state = docker_state("f1_ingestion")
            dbt_state = docker_state("f1_dbt")
            postgres_state = docker_state("f1_postgres")
            metabase_state = docker_state("f1_metabase")

            # ingestion failure 
            if ingestion_state == "exited":
                exit_code = docker_exit_code("f1_ingestion")
                if exit_code and exit_code != "0":
                    break

            # dbt failure 
            if dbt_state == "exited":
                exit_code = docker_exit_code("f1_dbt")
                if exit_code and exit_code != "0":
                    break

            # user ran docker compose down
            if (
                postgres_state == "not_created"
                and ingestion_state == "not_created"
                and dbt_state == "not_created"
                and metabase_state == "not_created"
            ):
                break

            # full success condition
            if (
                ingestion_state == "exited"
                and docker_exit_code("f1_ingestion") == "0"
                and dbt_state == "exited"
                and docker_exit_code("f1_dbt") == "0"
                and metabase_state == "running"
            ):
                break

            time.sleep(1)

    # final pipeline state

    postgres_state = docker_state("f1_postgres")
    ingestion_state = docker_state("f1_ingestion")
    dbt_state = docker_state("f1_dbt")
    restore_state = docker_state("f1_metabase_restore")
    metabase_state = docker_state("f1_metabase")

    ingestion_exit = docker_exit_code("f1_ingestion")
    dbt_exit = docker_exit_code("f1_dbt")
    restore_exit = docker_exit_code("f1_metabase_restore")

    # user stopped docker
    if all(
        s == "not_created"
        for s in [
            postgres_state,
            ingestion_state,
            dbt_state,
            restore_state,
            metabase_state,
        ]
    ):
        console.print("\n[bold yellow]⚠ Pipeline stopped by user.[/bold yellow]")

    # succes
    elif (
        postgres_state == "running"
        and ingestion_exit == "0"
        and dbt_exit == "0"
        and restore_exit == "0"
        and metabase_state == "running"
    ):
        console.print("\n[bold green]✅ Pipeline completed successfully.[/bold green]")
        render_pipeline_summary(start_time)

    # fail
    elif ingestion_exit and ingestion_exit != "0":
        console.print("\n[bold red]❌ Pipeline failed during ingestion.[/bold red]")

    elif dbt_exit and dbt_exit != "0":
        console.print("\n[bold red]❌ Pipeline failed during dbt models.[/bold red]")

    elif restore_exit and restore_exit != "0":
        console.print("\n[bold red]❌ Pipeline failed during Metabase restore.[/bold red]")

    elif postgres_state != "running":
        console.print("\n[bold red]❌ PostgreSQL container stopped unexpectedly.[/bold red]")

    elif metabase_state != "running":
        console.print("\n[bold red]❌ Metabase failed to start.[/bold red]")


if __name__ == "__main__":
    main()