import sys
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
from rich.text import Text
from rich.align import Align

from config.database import get_db_cursor

console = Console()

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
    seasons = seasons or 0

    laps = int(results * 60)
    distance = int(laps * 5)

    grid = Table.grid(expand=True)
    grid.add_column(width=2)  
    grid.add_column(justify="left")
    grid.add_column(justify="right")

    grid.add_row("🏁", Text("Seasons processed", style="cyan"), f"{seasons}")
    grid.add_row("🏎", Text("Grand Prix races", style="cyan"), f"{races:,}")
    grid.add_row("📊", Text("Driver results", style="cyan"), f"{results:,}")

    grid.add_row("", "", "")

    grid.add_row("😎", Text("Drivers ingested", style="cyan"), f"{drivers:,}")
    grid.add_row("🏭", Text("Constructors", style="cyan"), f"{constructors:,}")

    grid.add_row("", "", "")

    grid.add_row("🔁", Text("Laps estimated", style="cyan"), f"~{laps:,}")
    grid.add_row("📏", Text("Distance covered", style="cyan"), f"~{distance:,} km")

    grid.add_row("", "", "")

    grid.add_row("🧭", Text("Pipeline runtime", style="bold cyan"), Text(runtime, style="bold cyan"))

    panel = Panel(
        grid,
        title="🏁 F1 Pipeline Summary",
        border_style="bright_blue",
        padding=(1, 4),
        width=min(shutil.get_terminal_size().columns - 4, 70),
    )

    console.print(panel)

    console.print("\n[bold cyan]📊 Dashboard available at:[/bold cyan]")
    console.print("[blue]http://localhost:3000[/blue]\n")

# Database pooling

def get_ingestion_progress():
    path = Path("ingestion/logs/ingestion_progress.json")
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except:
        return None
    
    
def format_runtime(seconds):
    minutes, sec = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)

    if hours > 0:
        return f"{hours}h {minutes}m {sec}s"
    elif minutes > 0:
        return f"{minutes}m {sec}s"
    else:
        return f"{sec}s"

# Dashboard 

def render_dashboard(start_time):

    grid = Table.grid(expand=True)
    grid.add_column(justify="left")
    grid.add_column(justify="right")

    # postgres
    pg_health = docker_health("f1_postgres")

    if pg_health == "healthy":
        pg_status = Text("✓ Healthy", style="green")
    else:
        pg_status = Spinner("dots", text="Starting...", style="yellow")

    grid.add_row("[dim]\\[1/5][/dim] PostgreSQL", pg_status)
    grid.add_row("", "")

    # ingestion
    progress_data = get_ingestion_progress()
    ingest_state = docker_state("f1_ingestion")

    if ingest_state == "exited":

        exit_code = docker_exit_code("f1_ingestion")

        if exit_code == "0":
            ingest_status = Text("✓ Completed", style="green")
        elif exit_code == "2":
            ingest_status = Text("API limit", style="red")
        else:
            ingest_status = Text("Failed", style="red")

        grid.add_row("[dim]\\[2/5][/dim] Ingestion", ingest_status)

    elif progress_data:

        stage = progress_data.get("stage")

        if stage != "results":

            grid.add_row(
                "[dim]\\[2/5][/dim] Ingestion",
                Spinner("dots", text=f"{stage.capitalize()}...", style="yellow")
            )

        else:

            season = progress_data.get("season_index", 0)
            total_seasons = progress_data.get("total_seasons", 1)
            total_inserted = progress_data.get("total_inserted", 0)
            status = progress_data.get("status", "running")

            ratio = season / total_seasons
            percent = int(ratio * 100)

            progress_bar = Progress(
                BarColumn(bar_width=32, complete_style="magenta", finished_style="green"),
                TextColumn("{task.percentage:>3.0f}%", style="bold white"),
                expand=False,
            )
            progress_bar.add_task("results", total=100, completed=percent)

            progress_layout = Align.right(progress_bar)
        
            grid.add_row("[dim]\\[2/5][/dim] Ingestion", "")
            grid.add_row("", "")

            grid.add_row("Historical Results", progress_layout)

            grid.add_row("", "")

            estimated_laps = progress_data.get("estimated_laps", 0)
            estimated_distance = progress_data.get("estimated_distance_km", 0)

            stats_grid = Table.grid()
            stats_grid.add_column(style="dim", min_width=16)
            stats_grid.add_column(justify="right", min_width=14)
            stats_grid.add_row("Season", f"{season} / {total_seasons}")
            stats_grid.add_row("Driver Results", f"{total_inserted:,}")
            stats_grid.add_row("Laps", f"~{estimated_laps:,}")
            stats_grid.add_row("Distance", f"~{estimated_distance:,} km")

            grid.add_row("", Align.right(stats_grid))

            # API cooldown
            if status == "cooldown":

                sleep = progress_data.get("sleep_seconds", 0)

                grid.add_row("", "")
                grid.add_row("", Spinner("dots", text=f"API rate limit — cooling down {sleep}s", style="red"))

    else:

        grid.add_row(
            "[dim]\\[2/5][/dim] Ingestion",
            Spinner("dots", text="Pending...", style="yellow")
        )

    grid.add_row("", "")

    # dbt
    dbt_state = docker_state("f1_dbt")
    ingestion_state = docker_state("f1_ingestion")

    if dbt_state == "exited":
        dbt_status = Text("✓ Completed", style="green")
    elif dbt_state == "running" and ingestion_state != "exited":
        dbt_status = Spinner("dots", text="Pending...", style="yellow")
    elif dbt_state == "running" and ingestion_state == "exited":
        dbt_status = Spinner("dots", text="Running models...", style="yellow")
    else:
        dbt_status = Spinner("dots", text="Pending...", style="yellow")

    grid.add_row("[dim]\\[3/5][/dim] dbt Models", dbt_status)
    grid.add_row("", "")

    # metabase restore
    restore_state = docker_state("f1_metabase_restore")

    if restore_state == "exited":
        restore_status = Text("✓ Completed", style="green")
    elif restore_state == "running":
        restore_status = Spinner("dots", text="Restoring...", style="yellow")
    else:
        restore_status = Spinner("dots", text="Pending...", style="yellow")

    grid.add_row("[dim]\\[4/5][/dim] Metabase Restore", restore_status)
    grid.add_row("", "")

    # metabase
    meta_health = docker_health("f1_metabase")

    if meta_health == "healthy":
        meta_status = Text("✓ Healthy", style="green")
    else:
        meta_status = Spinner("dots", text="Starting...", style="yellow")

    grid.add_row("[dim]\\[5/5][/dim] Dashboard", meta_status)
    grid.add_row("", "")

    # runtime
    elapsed = format_runtime(time.time() - start_time)

    grid.add_row("[dim]─────────────────────[/dim]", "[dim]─────────────[/dim]")
    grid.add_row(Text("Elapsed Time", style="cyan"), Text(elapsed, style="cyan"))

    return Panel(
        grid,
        title="🚀 F1 Data Warehouse Pipeline",
        border_style="bright_blue",
        padding=(1, 4),
    )



def docker_exit_code(container):
    try:
        return subprocess.check_output(
            ["docker", "inspect", "-f", "{{.State.ExitCode}}", container],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except:
        return None


def main():

    # CLI flag
    if "--summary" in sys.argv:
        render_pipeline_summary(time.time())
        return

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
        console.print()
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