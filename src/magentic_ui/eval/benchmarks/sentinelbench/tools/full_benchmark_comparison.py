#!/usr/bin/env python3
"""
🚀 SentinelBench Task Comparison Runner

Beautiful CLI tool to compare performance between "With Sentinel" vs "Without Sentinel"
across all SentinelBench tasks with comprehensive analysis and visualizations.

This script:
1. 🔍 Finds tasks with data in both directories
2. 🔄 Runs individual task analyses with dimension alignment
3. 📁 Combines CSV files with consistent formatting
4. 📈 Generates comparison plots and statistics

Usage Examples:
    # Recommended: Complete evaluation with union alignment
    python full_benchmark_comparison.py --model gpt-5-mini --union-fill

    # Conservative: Only shared dimensions
    python full_benchmark_comparison.py --model gpt-5-mini --intersection-only

    # Quick test: Skip individual analysis
    python full_benchmark_comparison.py --model gpt-5-mini --skip-individual
"""

import subprocess
import os
import json
import pandas as pd  # type: ignore
from pathlib import Path
from typing import List, Dict, Annotated, Tuple, Optional, cast
import logging
import typer
import sys

# Import from centralized task variants
sys.path.append(str(Path(__file__).parent.parent))
try:
    from task_variants import EXPECTED_DIMENSIONS  # type: ignore
except ImportError:
    # Fallback to local definition if import fails
    expected_dimensions: Dict[str, List[int]] = {}
    EXPECTED_DIMENSIONS = expected_dimensions  # type: ignore

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_expected_tasks() -> Tuple[List[str], Dict[str, str]]:
    """Load expected task IDs and passwords from test.jsonl file."""
    jsonl_path = Path(
        "/home/matheus/projects/magentic-ui/data/SentinelBench/test.jsonl"
    )

    if not jsonl_path.exists():
        logger.error(f"test.jsonl not found at {jsonl_path}")
        return [], {}

    tasks: List[str] = []
    task_passwords: Dict[str, str] = {}

    with open(jsonl_path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    task_data = json.loads(line)
                    task_id = task_data["id"]
                    password = task_data.get("password", "")

                    tasks.append(task_id)
                    task_passwords[task_id] = password

                except json.JSONDecodeError:
                    logger.warning(f"Skipping invalid JSON line: {line}")
                    continue

    logger.info(f"Loaded {len(tasks)} tasks with passwords from test.jsonl")
    return tasks, task_passwords


def check_run_exists(run_dir: Path, task_name: str, dimension: int) -> bool:
    """Check if a run exists (regardless of success/failure)."""
    task_dir = run_dir / task_name / str(dimension)

    if not task_dir.exists():
        return False

    # Check for required files
    times_file = task_dir / "times.json"
    answer_files = list(task_dir.glob(f"{task_name}_{dimension}_answer.json"))
    tokens_file = task_dir / "model_tokens_usage.json"

    return times_file.exists() and len(answer_files) > 0 and tokens_file.exists()


def check_run_validity(
    run_dir: Path,
    task_name: str,
    dimension: int,
    expected_password: str,
    check_messages: bool = False,
) -> bool:
    """Check if a run exists and is SUCCESSFUL (contains the correct password)."""
    task_dir = run_dir / task_name / str(dimension)

    if not task_dir.exists():
        return False

    # Check for required files
    times_file = task_dir / "times.json"
    answer_files = list(task_dir.glob(f"{task_name}_{dimension}_answer.json"))
    tokens_file = task_dir / "model_tokens_usage.json"

    if not (times_file.exists() and len(answer_files) > 0 and tokens_file.exists()):
        return False

    if not expected_password:
        logger.warning(f"No expected password for {task_name}_{dimension}")
        return False

    # Construct the expected password with parameter: BASEPASSWORD_PARAMETER
    expected_full_password = f"{expected_password}_{dimension}".upper()

    if check_messages:
        # Check messages.json for any mention of the password (case-insensitive)
        messages_files = list(task_dir.glob(f"{task_name}_{dimension}_messages.json"))
        if not messages_files:
            return False

        try:
            with open(messages_files[0], "r") as f:
                messages_content = f.read().upper()
                return expected_full_password in messages_content
        except (FileNotFoundError, UnicodeDecodeError) as e:
            logger.warning(
                f"Could not read messages file for {task_name}_{dimension}: {e}"
            )
            return False
    else:
        # Check answer.json for exact match (case-insensitive)
        try:
            with open(answer_files[0]) as f:
                answer_data = json.load(f)
                answer = answer_data.get("answer", "").upper()

                # Check for timeout first
                if "TIMEOUT" in answer:
                    return False

                # Check for exact match of BASEPASSWORD_PARAMETER
                return answer == expected_full_password

        except (json.JSONDecodeError, FileNotFoundError, KeyError):
            return False


def find_common_tasks() -> List[str]:
    """Find tasks that have at least some runs (including failed runs) in both directories."""
    base_path = Path("runs/MagenticUI_web_surfer_only/SentinelBench/test")
    expected_tasks, _ = load_expected_tasks()  # task_passwords unused in this function

    tasks_with_data_in_both: List[str] = []

    for task_name in expected_tasks:
        if task_name not in EXPECTED_DIMENSIONS:
            logger.warning(f"Task '{task_name}' not in expected dimensions. Skipping.")
            continue

        expected_dims: List[int] = cast(List[int], EXPECTED_DIMENSIONS[task_name])

        # Check if task has any runs (including failed runs) in both directories
        dir0_has_data = False
        dir1_has_data = False

        for dimension in expected_dims:
            # Always use check_run_exists to include failed runs by default
            if check_run_exists(base_path / "0", task_name, dimension):
                dir0_has_data = True
            if check_run_exists(base_path / "1", task_name, dimension):
                dir1_has_data = True

        if dir0_has_data and dir1_has_data:
            tasks_with_data_in_both.append(task_name)
            logger.info(f"✅ {task_name}: Has runs in both directories")
        else:
            logger.info(
                f"❌ {task_name}: Missing runs in {'dir 0' if not dir0_has_data else 'dir 1'}"
            )

    return tasks_with_data_in_both


def run_analyze_dimensions(
    task_name: str,
    model: str,
    output_dir: str,
    intersection_only: bool = False,
    union_fill: bool = False,
) -> Tuple[Optional[str], Optional[str]]:
    """Run single_task_performance.py for a specific task and return CSV file paths."""

    cmd = [
        "python",
        "src/magentic_ui/eval/benchmarks/sentinelbench/tools/single_task_performance.py",
        "--run-dir",
        "runs/MagenticUI_web_surfer_only/SentinelBench/test/0/",
        "--compare-with",
        "runs/MagenticUI_web_surfer_only/SentinelBench/test/1/",
        "--task-name",
        task_name,
        "--model",
        model,
        "--main-label",
        "Without Sentinel",
        "--compare-label",
        "With Sentinel",
        "--output-dir",
        output_dir,
        "--save-csv",
        "--combined",
    ]

    # Add intersection/union flags if specified
    if intersection_only:
        cmd.append("--intersection-only")
    if union_fill:
        cmd.append("--union-fill")

    logger.info(f"Running analysis for {task_name}...")

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info(f"✅ Successfully analyzed {task_name}")

        # Return expected CSV file paths
        base_name = f"{task_name.replace('/', '_').replace(' ', '_')}-comparison"
        csv_without = os.path.join(
            output_dir, f"{base_name}_without_sentinel_analysis.csv"
        )
        csv_with = os.path.join(output_dir, f"{base_name}_with_sentinel_analysis.csv")

        return csv_without, csv_with

    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Failed to analyze {task_name}: {e}")
        logger.error(f"STDERR: {e.stderr}")
        return None, None


def combine_csv_files(
    csv_file_pairs: List[Tuple[Optional[str], Optional[str]]], output_dir: str
) -> Tuple[Optional[str], Optional[str]]:
    """Combine individual task CSV files into overall comparison files."""

    all_without_sentinel: List[pd.DataFrame] = []  # type: ignore
    all_with_sentinel: List[pd.DataFrame] = []  # type: ignore

    for csv_without, csv_with in csv_file_pairs:
        if (
            csv_without
            and csv_with
            and os.path.exists(csv_without)
            and os.path.exists(csv_with)
        ):
            try:
                df_without = pd.read_csv(csv_without)  # type: ignore
                df_with = pd.read_csv(csv_with)  # type: ignore

                all_without_sentinel.append(df_without)
                all_with_sentinel.append(df_with)

                logger.info(f"✅ Added data from {os.path.basename(csv_without)}")
            except Exception as e:
                logger.error(f"❌ Failed to read CSV files: {e}")

    if not all_without_sentinel or not all_with_sentinel:
        logger.error("No valid CSV files found to combine")
        return None, None

    # Combine all dataframes
    combined_without = pd.concat(all_without_sentinel, ignore_index=True)
    combined_with = pd.concat(all_with_sentinel, ignore_index=True)

    # Rename task_name to task_id for compatibility with compare_sentinel_performance.py
    if "task_name" in combined_without.columns:
        combined_without = combined_without.rename(columns={"task_name": "task_id"})
    if "task_name" in combined_with.columns:
        combined_with = combined_with.rename(columns={"task_name": "task_id"})

    # Save combined files
    combined_without_path = os.path.join(output_dir, "all_tasks_without_sentinel.csv")
    combined_with_path = os.path.join(output_dir, "all_tasks_with_sentinel.csv")

    combined_without.to_csv(combined_without_path, index=False)  # type: ignore
    combined_with.to_csv(combined_with_path, index=False)  # type: ignore

    logger.info("✅ Combined CSV files saved:")
    logger.info(
        f"   Without sentinel: {combined_without_path} ({len(combined_without)} rows)"
    )
    logger.info(f"   With sentinel: {combined_with_path} ({len(combined_with)} rows)")

    return combined_without_path, combined_with_path


def run_comparison_analysis(
    csv_without: str, csv_with: str, model: str, output_dir: str
):
    """Run the overall comparison analysis."""

    cmd = [
        "python",
        "experiments/eval/compare_sentinel_performance.py",
        "--non-sentinel-csv",
        csv_without,
        "--sentinel-csv",
        csv_with,
        "--model",
        model,
        "--output-dir",
        output_dir,
        "--output-prefix",
        "all_tasks_comparison",
    ]

    logger.info("Running overall comparison analysis...")

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info("✅ Successfully completed comparison analysis")
        print(result.stdout)  # Show the summary statistics

    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Failed to run comparison analysis: {e}")
        logger.error(f"STDERR: {e.stderr}")


def main(
    # 🎯 Core Configuration
    model: Annotated[
        str, typer.Option(help="🤖 Model name for cost calculation (e.g., gpt-5-mini)")
    ],
    output_dir: Annotated[
        str,
        typer.Option("--output-dir", help="📁 Directory to save plots and CSV files"),
    ] = "plots/FINAL",
    # 🔍 Data Selection & Filtering
    check_messages: Annotated[
        bool,
        typer.Option(
            "--check-messages",
            help="📝 Use messages.json for password validation instead of exact answer match",
        ),
    ] = False,
    # ⚖️ Dimension Alignment (choose one)
    intersection_only: Annotated[
        bool,
        typer.Option(
            "--intersection-only",
            help="🔗 Only include dimensions present in BOTH directories (AND operation)",
        ),
    ] = False,
    union_fill: Annotated[
        bool,
        typer.Option(
            "--union-fill",
            help="🔄 Include ALL dimensions, fill missing with artificial entries (UNION operation)",
        ),
    ] = False,
    # ⚙️ Processing Options
    skip_individual: Annotated[
        bool,
        typer.Option(
            "--skip-individual",
            help="⏩ Skip individual task analysis, only do combined analysis",
        ),
    ] = False,
):
    """
    🚀 **SentinelBench Task Comparison Runner**

    Compare performance between "With Sentinel" vs "Without Sentinel" across all SentinelBench tasks.

    **🏆 Recommended for complete evaluation:**
    ```
    python comparison_runner.py --model gpt-5-mini --union-fill
    ```

    **📊 This will:**
    - Include all attempted tasks (even failures)
    - Align dimensions across both runs
    - Generate comprehensive comparison plots & statistics
    """

    # Validate intersection/union flags
    if intersection_only and union_fill:
        typer.echo(
            "❌ Cannot use both --intersection-only and --union-fill flags simultaneously",
            err=True,
        )
        typer.echo(
            "💡 Choose one: --intersection-only (AND) or --union-fill (UNION)", err=True
        )
        raise typer.Exit(1)

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Pretty status messages
    typer.echo("🔍 Finding tasks with data in directories...")
    if check_messages:
        typer.echo("📝 Using messages.json for password validation (substring search)")
    else:
        typer.echo("🎯 Using answer.json for password validation (exact match)")

    if union_fill:
        typer.echo(
            "🔄 Union mode: Including ALL dimensions, filling missing with artificial entries"
        )
    elif intersection_only:
        typer.echo(
            "🔗 Intersection mode: Only including dimensions present in BOTH directories"
        )
    else:
        typer.echo(
            "📊 Default mode: Including available dimensions from each directory independently"
        )

    common_tasks = find_common_tasks()

    if not common_tasks:
        typer.echo("❌ No tasks found with data in directories!", err=True)
        typer.echo("💡 Check that evaluation runs exist in both directories", err=True)
        raise typer.Exit(1)

    typer.echo(f"📊 Found {len(common_tasks)} tasks to analyze")

    csv_file_pairs: List[Tuple[Optional[str], Optional[str]]] = []

    if not skip_individual:
        # Step 1: Run individual task analyses
        typer.echo("🔄 Running individual task analyses...")
        with typer.progressbar(common_tasks, label="Analyzing tasks") as tasks:
            for task_name in tasks:
                csv_without, csv_with = run_analyze_dimensions(
                    task_name, model, output_dir, intersection_only, union_fill
                )
                if csv_without and csv_with:
                    csv_file_pairs.append((csv_without, csv_with))

    # Step 2: Combine CSV files
    typer.echo("📁 Combining CSV files...")
    combined_without, combined_with = combine_csv_files(csv_file_pairs, output_dir)

    if not combined_without or not combined_with:
        typer.echo("❌ Failed to create combined CSV files!", err=True)
        raise typer.Exit(1)

    # Step 3: Run overall comparison
    typer.echo("📈 Running overall comparison analysis...")
    run_comparison_analysis(combined_without, combined_with, model, output_dir)

    typer.echo(f"🎉 All done! Results saved to {output_dir}/")
    typer.echo(f"📂 Check out: {output_dir}/all_tasks_comparison_*.png for plots!")


if __name__ == "__main__":
    typer.run(main)
