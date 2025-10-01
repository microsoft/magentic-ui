#!/usr/bin/env python3
# type: ignore[reportUnknownMemberType,reportUnknownVariableType,reportMissingTypeStubs]
"""
Analyze SentinelBench performance across task dimensions.
Creates plots showing accuracy, latency, and cost scaling for specific tasks.
Supports both single run analysis and comparison between two runs.

Usage:
    # Single run analysis without sentinel:
    python single_task_performance.py \
                                 --run-dir runs/MagenticUI_web_surfer_only/SentinelBench/test/0 \
                                 --task-name button-presser \
                                 --model gpt-5-mini \
                                 --output-dir plots/button-presser \
    
    # Single run analysis with sentinel:
    python single_task_performance.py \
                                 --run-dir runs/MagenticUI_web_surfer_only/SentinelBench/test/1 \
                                 --task-name button-presser \
                                 --model gpt-5-mini \
                                 --output-dir plots/button-presser \
                                 --sentinel

    # Comparison between two runs (e.g., with vs without sentinel):
    python single_task_performance.py \
                                 --run-dir runs/MagenticUI_web_surfer_only/SentinelBench/test/0 \
                                 --compare-with runs/MagenticUI_web_surfer_only/SentinelBench/test/1 \
                                 --task-name button-presser \
                                 --model gpt-5-mini \
                                 --main-label "Without Sentinel" \
                                 --compare-label "With Sentinel" \
                                 --output-dir plots/button-presser \
                                 --combined
"""

import matplotlib.pyplot as plt  # type: ignore
from matplotlib.ticker import PercentFormatter, FuncFormatter  # type: ignore
import pandas as pd  # type: ignore
import numpy as np  # type: ignore
import typer  # type: ignore
from typing_extensions import Annotated
import os
import json
from typing import Optional
from pathlib import Path
import logging

# Import model pricing from task_variants
from ..task_variants import MODEL_PRICING

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def format_time_dimension(seconds: int) -> str:
    """Format time dimension for display on plots."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}m"
    else:
        hours = seconds // 3600
        remaining_minutes = (seconds % 3600) // 60
        if remaining_minutes == 0:
            return f"{hours}h"
        else:
            return f"{hours}h{remaining_minutes}m"


def is_duration_task(task_name: str) -> bool:
    """Check if a task is duration-based (vs count-based)."""
    duration_patterns = [
        "reactor",
        "linkedin-monitor",
        "news-checker",
        "teams-monitor",
        "flight-monitor",
        "github-watcher",
    ]
    return any(pattern in task_name for pattern in duration_patterns)


def setup_plot_style():
    """Set up beautiful, paper-ready plot styling with light purple cartoonish theme."""
    # Use a clean, modern style as base
    plt.style.use("default")  # type: ignore

    # Font settings for NeurIPS-style academic papers
    plt.rcParams["font.family"] = "serif"  # type: ignore
    plt.rcParams["font.serif"] = [
        "Times",
        "Computer Modern Roman",
        "CMU Serif",
        "Liberation Serif",
        "DejaVu Serif",
        "serif",
    ]
    plt.rcParams["font.size"] = 14
    plt.rcParams["axes.labelsize"] = 16
    plt.rcParams["axes.titlesize"] = 18
    plt.rcParams["xtick.labelsize"] = 13
    plt.rcParams["ytick.labelsize"] = 13
    plt.rcParams["legend.fontsize"] = 14
    plt.rcParams["figure.titlesize"] = 20

    # High-quality settings for publication
    plt.rcParams["figure.dpi"] = 150
    plt.rcParams["savefig.dpi"] = 300
    plt.rcParams["savefig.bbox"] = "tight"
    plt.rcParams["savefig.pad_inches"] = 0.1

    # Beautiful color scheme
    plt.rcParams["axes.prop_cycle"] = plt.cycler(
        "color",
        [
            "#9D7FE0",  # Light purple
            "#B19FE8",  # Lighter purple
            "#C5BFF0",  # Very light purple
            "#E8E3F8",  # Pale purple
            "#F5F3FC",  # Almost white purple
        ],
    )

    # Clean, modern appearance
    plt.rcParams["axes.spines.top"] = False
    plt.rcParams["axes.spines.right"] = False
    plt.rcParams["axes.spines.left"] = True
    plt.rcParams["axes.spines.bottom"] = True
    plt.rcParams["axes.linewidth"] = 1.2
    plt.rcParams["axes.edgecolor"] = "#666666"

    # Grid styling
    plt.rcParams["axes.grid"] = True
    plt.rcParams["grid.alpha"] = 0.3
    plt.rcParams["grid.linewidth"] = 0.8
    plt.rcParams["grid.color"] = "#CCCCCC"

    # Background colors
    plt.rcParams["figure.facecolor"] = "white"
    plt.rcParams["axes.facecolor"] = "#FEFEFE"


def calculate_cost(prompt_tokens: int, completion_tokens: int, model: str) -> float:
    """Calculate cost for a task based on token usage and model pricing."""
    if model not in MODEL_PRICING:
        logger.warning(f"Unknown model: {model}. Using gpt-4o pricing as default.")
        model = "gpt-4o"

    pricing = MODEL_PRICING[model]

    # Calculate cost per 1K tokens
    input_cost = (prompt_tokens / 1000) * pricing["input"]
    output_cost = (completion_tokens / 1000) * pricing["output"]

    return input_cost + output_cost


def load_task_data(run_dir: str, task_name: str) -> pd.DataFrame:
    """
    Load task data from run directory for a specific task across all dimensions.

    Args:
        run_dir: Path to run directory (e.g., runs/MagenticUI/SentinelBench/test/4000)
        task_name: Name of the task (e.g., animal-mover-easy)

    Returns:
        DataFrame with columns: dimension, duration, answer, prompt_tokens, completion_tokens, completed, has_timeout
    """
    data = []
    run_path = Path(run_dir)

    # Find all subdirectories matching the task name
    task_dirs = [
        d for d in run_path.iterdir() if d.is_dir() and d.name.startswith(task_name)
    ]

    if not task_dirs:
        raise ValueError(f"No directories found for task '{task_name}' in {run_dir}")

    for task_dir in task_dirs:
        # Extract dimension from directory name (e.g., animal-mover-easy -> look for subdirectories with dimensions)
        for dim_dir in task_dir.iterdir():
            if not dim_dir.is_dir():
                continue

            try:
                dimension = int(dim_dir.name)
            except ValueError:
                continue  # Skip non-numeric directories

            task_data = {"task_name": task_name, "dimension": dimension}

            # Load timing data
            times_file = dim_dir / "times.json"
            if times_file.exists():
                with open(times_file) as f:
                    times_data = json.load(f)
                    task_data["duration"] = times_data.get("duration", 0)
                    task_data["completed"] = times_data.get("completed", False)
                    task_data["interrupted"] = times_data.get("interrupted", False)
            else:
                logger.warning(
                    f"No times.json found for {task_name} dimension {dimension}"
                )
                continue

            # Load answer data
            answer_files = list(dim_dir.glob(f"{task_name}_{dimension}_answer.json"))
            if answer_files:
                with open(answer_files[0]) as f:
                    answer_data = json.load(f)
                    task_data["answer"] = answer_data.get("answer", "")
            else:
                logger.warning(
                    f"No answer file found for {task_name} dimension {dimension}"
                )
                task_data["answer"] = ""

            # Load token usage data
            tokens_file = dim_dir / "model_tokens_usage.json"
            if tokens_file.exists():
                with open(tokens_file) as f:
                    token_data = json.load(f)
                    total_data = token_data.get("total_without_user_proxy", {})
                    task_data["prompt_tokens"] = total_data.get("prompt_tokens", 0)
                    task_data["completion_tokens"] = total_data.get(
                        "completion_tokens", 0
                    )
                    task_data["total_tokens"] = (
                        task_data["prompt_tokens"] + task_data["completion_tokens"]
                    )
            else:
                logger.warning(
                    f"No token usage file found for {task_name} dimension {dimension}"
                )
                task_data["prompt_tokens"] = 0
                task_data["completion_tokens"] = 0
                task_data["total_tokens"] = 0

            # Determine if task has timeout pattern
            task_data["has_timeout"] = "TIMEOUT" in task_data.get("answer", "").upper()

            # Load evaluation score (if available)
            score_file = dim_dir / "score.json"
            if score_file.exists():
                with open(score_file) as f:
                    score_data = json.load(f)
                    task_data["score"] = score_data.get("score", 0.0)
            else:
                logger.warning(
                    f"No score.json found for {task_name} dimension {dimension}"
                )
                task_data["score"] = None

            data.append(task_data)

    if not data:
        raise ValueError(f"No valid data found for task '{task_name}'")

    df = pd.DataFrame(data)
    df = df.sort_values("dimension")  # Sort by dimension

    logger.info(f"Loaded data for {len(df)} dimension variants of task '{task_name}'")
    logger.info(f"Dimensions found: {sorted(df['dimension'].unique())}")

    return df


def create_artificial_entry(task_name: str, dimension: int, run_label: str) -> dict:
    """Create an artificial entry for a missing task+dimension combination."""
    return {
        "task_name": task_name,
        "dimension": dimension,
        "duration": 0,
        "completed": False,
        "interrupted": False,
        "answer": "MANUALLYPOPULATED",
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "has_timeout": False,
        "score": 0.0,
        "run_type": run_label,
    }


def load_comparison_data(
    run_dir: str,
    compare_dir: str,
    task_name: str,
    intersection_only: bool,
    union_fill: bool,
    main_label: str,
    compare_label: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load task data for comparison with intersection/union modes.

    Args:
        run_dir: Path to main run directory
        compare_dir: Path to comparison run directory
        task_name: Name of the task to analyze
        intersection_only: If True, only include dimensions present in both directories
        union_fill: If True, include all dimensions, filling missing ones with artificial entries
        main_label: Label for main run data
        compare_label: Label for comparison run data

    Returns:
        Tuple of (main_df, compare_df) DataFrames
    """
    # Load data from both directories (may fail if task doesn't exist)
    df_main = None
    df_compare = None

    try:
        df_main = load_task_data(run_dir, task_name)
    except ValueError:
        logger.warning(f"Task '{task_name}' not found in main directory: {run_dir}")

    try:
        df_compare = load_task_data(compare_dir, task_name)
    except ValueError:
        logger.warning(
            f"Task '{task_name}' not found in comparison directory: {compare_dir}"
        )

    # If neither directory has the task, return empty DataFrames
    if df_main is None and df_compare is None:
        empty_df = pd.DataFrame()
        return empty_df, empty_df

    # Handle cases where only one directory has the task
    if df_main is None:
        df_main = pd.DataFrame()
    if df_compare is None:
        df_compare = pd.DataFrame()

    # Get dimensions from both DataFrames
    main_dimensions = set(df_main["dimension"].tolist()) if len(df_main) > 0 else set()
    compare_dimensions = (
        set(df_compare["dimension"].tolist()) if len(df_compare) > 0 else set()
    )

    if intersection_only:
        # Only keep dimensions that exist in both
        common_dimensions = main_dimensions & compare_dimensions
        logger.info(
            f"Intersection mode: keeping {len(common_dimensions)} common dimensions: {sorted(common_dimensions)}"
        )

        if len(df_main) > 0:
            df_main = df_main[df_main["dimension"].isin(common_dimensions)]
        if len(df_compare) > 0:
            df_compare = df_compare[df_compare["dimension"].isin(common_dimensions)]

    elif union_fill:
        # Include all dimensions, filling missing ones
        all_dimensions = main_dimensions | compare_dimensions
        logger.info(
            f"Union mode: including {len(all_dimensions)} total dimensions: {sorted(all_dimensions)}"
        )

        # Add missing dimensions to main
        missing_in_main = compare_dimensions - main_dimensions
        if missing_in_main:
            logger.info(
                f"Adding {len(missing_in_main)} artificial entries to main: {sorted(missing_in_main)}"
            )
            artificial_main = [
                create_artificial_entry(task_name, dim, main_label)
                for dim in missing_in_main
            ]
            df_main = pd.concat(
                [df_main, pd.DataFrame(artificial_main)], ignore_index=True
            )

        # Add missing dimensions to compare
        missing_in_compare = main_dimensions - compare_dimensions
        if missing_in_compare:
            logger.info(
                f"Adding {len(missing_in_compare)} artificial entries to compare: {sorted(missing_in_compare)}"
            )
            artificial_compare = [
                create_artificial_entry(task_name, dim, compare_label)
                for dim in missing_in_compare
            ]
            df_compare = pd.concat(
                [df_compare, pd.DataFrame(artificial_compare)], ignore_index=True
            )

    # Add run_type labels if they don't already exist
    if len(df_main) > 0 and "run_type" not in df_main.columns:
        df_main["run_type"] = main_label
    if len(df_compare) > 0 and "run_type" not in df_compare.columns:
        df_compare["run_type"] = compare_label

    # Sort by dimension for consistent ordering
    if len(df_main) > 0:
        df_main = df_main.sort_values("dimension")
    if len(df_compare) > 0:
        df_compare = df_compare.sort_values("dimension")

    return df_main, df_compare


def analyze_accuracy(df: pd.DataFrame) -> pd.DataFrame:
    """
    Analyze accuracy based on evaluation scores from score.json files.
    Only considers tasks with exact evaluation scores (score == 1.0) as successful.
    """
    # Check if we have evaluation scores
    if "score" in df.columns and df["score"].notna().sum() > 0:
        # Use real evaluation scores - only perfect scores (1.0) count as success
        logger.info(
            "Using evaluation scores for accuracy analysis (only perfect scores count as success)"
        )
        df["accuracy"] = (df["score"] == 1.0).astype(int)
    else:
        # No fallback - if no evaluation scores, mark all as failed
        logger.error(
            "No evaluation scores found. Cannot determine accuracy without proper evaluation."
        )
        df["accuracy"] = 0

    # Group by dimension and calculate accuracy rate
    accuracy_by_dim = (
        df.groupby("dimension").agg({"accuracy": ["mean", "count"]}).round(4)
    )

    # Flatten column names
    accuracy_by_dim.columns = ["accuracy_rate", "total_tasks"]
    accuracy_by_dim = accuracy_by_dim.reset_index()

    return accuracy_by_dim


def plot_accuracy_vs_dimension(
    df: pd.DataFrame,
    task_name: str,
    sentinel: bool = False,
    save_path: Optional[str] = None,
):
    """Create accuracy vs dimension plot."""
    setup_plot_style()

    accuracy_data = analyze_accuracy(df)

    fig, ax = plt.subplots(figsize=(10, 6))

    dimensions = accuracy_data["dimension"]
    accuracy_rates = accuracy_data["accuracy_rate"] * 100  # Convert to percentage

    # Create evenly spaced x positions (treat dimensions as categorical)
    x_positions = range(len(dimensions))

    # Create beautiful bar plot with gradient effect
    bars = ax.bar(
        x_positions,
        accuracy_rates,
        color="#B19FE8",
        alpha=0.85,
        edgecolor="#7B68C7",
        linewidth=1.5,
        capstyle="round",
    )

    # Add elegant value labels on bars
    for i, (bar, acc) in enumerate(zip(bars, accuracy_rates)):
        height = bar.get_height()
        ax.text(
            i,
            height + 1,
            f"{acc:.1f}%",
            ha="center",
            va="bottom",
            fontweight="bold",
            fontsize=12,
            color="#5A4B7B",
        )

    sentinel_suffix = " (With Sentinel)" if sentinel else " (Without Sentinel)"
    ax.set_xlabel("Task Dimension", fontweight="bold")
    ax.set_ylabel("Success Rate (%)", fontweight="bold")
    ax.set_title(
        f'Success Rate vs Dimension: {task_name.replace("-", " ").title()}{sentinel_suffix}',
        fontweight="bold",
    )
    ax.set_ylim(0, 105)
    ax.yaxis.set_major_formatter(PercentFormatter())

    # Set x-axis with evenly spaced categorical labels
    ax.set_xticks(x_positions)
    ax.set_xticklabels(dimensions)

    # Beautiful grid styling (already set in rcParams)
    ax.set_axisbelow(True)

    plt.tight_layout()

    if save_path:
        accuracy_path = save_path.replace(".png", "_accuracy.png")
        plt.savefig(accuracy_path, dpi=300, bbox_inches="tight")
        plt.savefig(accuracy_path.replace(".png", ".pdf"), dpi=300, bbox_inches="tight")
        logger.info(f"Accuracy plot saved to {accuracy_path}")

    return fig, ax


def plot_accuracy_comparison(
    df_main: pd.DataFrame,
    df_compare: pd.DataFrame,
    task_name: str,
    main_label: str,
    compare_label: str,
    save_path: Optional[str] = None,
):
    """Create accuracy comparison plot with grouped bars."""
    setup_plot_style()

    # Analyze accuracy for both datasets
    accuracy_main = analyze_accuracy(df_main)
    accuracy_compare = analyze_accuracy(df_compare)

    fig, ax = plt.subplots(figsize=(12, 6))

    # Get common dimensions
    dimensions = sorted(
        set(accuracy_main["dimension"]) & set(accuracy_compare["dimension"])
    )

    # Prepare data for plotting
    main_rates = []
    compare_rates = []

    for dim in dimensions:
        main_row = accuracy_main[accuracy_main["dimension"] == dim]
        compare_row = accuracy_compare[accuracy_compare["dimension"] == dim]

        main_rates.append(
            main_row.iloc[0]["accuracy_rate"] * 100 if len(main_row) > 0 else 0
        )
        compare_rates.append(
            compare_row.iloc[0]["accuracy_rate"] * 100 if len(compare_row) > 0 else 0
        )

    # Create grouped bar chart
    x = np.arange(len(dimensions))
    width = 0.35

    bars1 = ax.bar(
        x - width / 2,
        main_rates,
        width,
        label=main_label,
        color="#B19FE8",
        alpha=0.85,
        edgecolor="#7B68C7",
        linewidth=1.5,
    )
    bars2 = ax.bar(
        x + width / 2,
        compare_rates,
        width,
        label=compare_label,
        color="#7B68C7",
        alpha=0.85,
        edgecolor="#5A4B7B",
        linewidth=1.5,
    )

    # Add value labels on bars
    for i, (bar1, bar2, rate1, rate2) in enumerate(
        zip(bars1, bars2, main_rates, compare_rates)
    ):
        height1 = bar1.get_height()
        height2 = bar2.get_height()

        ax.text(
            bar1.get_x() + bar1.get_width() / 2,
            height1 + 1,
            f"{rate1:.1f}%",
            ha="center",
            va="bottom",
            fontweight="bold",
            fontsize=10,
            color="#5A4B7B",
        )
        ax.text(
            bar2.get_x() + bar2.get_width() / 2,
            height2 + 1,
            f"{rate2:.1f}%",
            ha="center",
            va="bottom",
            fontweight="bold",
            fontsize=10,
            color="#5A4B7B",
        )

    ax.set_xlabel("Task Dimension", fontweight="bold")
    ax.set_ylabel("Success Rate (%)", fontweight="bold")
    ax.set_title(
        f'Success Rate Comparison: {task_name.replace("-", " ").title()}',
        fontweight="bold",
    )
    ax.set_ylim(0, 105)
    ax.yaxis.set_major_formatter(PercentFormatter())

    ax.set_xticks(x)
    ax.set_xticklabels(dimensions)
    ax.legend(fontsize=12, frameon=True, fancybox=True, shadow=True)
    ax.set_axisbelow(True)

    plt.tight_layout()

    if save_path:
        accuracy_path = save_path.replace(".png", "_accuracy_comparison.png")
        plt.savefig(accuracy_path, dpi=300, bbox_inches="tight")
        plt.savefig(accuracy_path.replace(".png", ".pdf"), dpi=300, bbox_inches="tight")
        logger.info(f"Accuracy comparison plot saved to {accuracy_path}")

    return fig, ax


def plot_latency_vs_dimension(
    df: pd.DataFrame,
    task_name: str,
    sentinel: bool = False,
    save_path: Optional[str] = None,
):
    """Create latency vs dimension plot."""
    setup_plot_style()

    # Group by dimension and calculate mean latency (in minutes)
    latency_data = (
        df.groupby("dimension").agg({"duration": ["mean", "std", "count"]}).round(2)
    )

    # Flatten column names
    latency_data.columns = ["mean_duration", "std_duration", "count"]
    latency_data = latency_data.reset_index()

    # Convert to minutes
    latency_data["mean_duration_min"] = latency_data["mean_duration"] / 60
    latency_data["std_duration_min"] = latency_data["std_duration"] / 60

    fig, ax = plt.subplots(figsize=(10, 6))

    dimensions = latency_data["dimension"]
    mean_latencies = latency_data["mean_duration_min"]
    std_latencies = latency_data["std_duration_min"]

    # Create evenly spaced x positions (treat dimensions as categorical)
    x_positions = range(len(dimensions))

    # Create beautiful bar plot with error bars
    bars = ax.bar(
        x_positions,
        mean_latencies,
        yerr=std_latencies,
        capsize=6,
        color="#9D7FE0",
        alpha=0.85,
        edgecolor="#6A5ACD",
        linewidth=1.5,
        capstyle="round",
        error_kw={"color": "#5A4B7B", "linewidth": 2},
    )

    # Add elegant value labels on bars
    for i, (bar, lat) in enumerate(zip(bars, mean_latencies)):
        height = bar.get_height()
        ax.text(
            i,
            height + max(std_latencies) * 0.1,
            f"{lat:.1f}m",
            ha="center",
            va="bottom",
            fontweight="bold",
            fontsize=12,
            color="#5A4B7B",
        )

    sentinel_suffix = " (With Sentinel)" if sentinel else " (Without Sentinel)"
    ax.set_xlabel("Task Dimension", fontweight="bold")
    ax.set_ylabel("Average Duration (minutes)", fontweight="bold")
    ax.set_title(
        f'Task Duration vs Dimension: {task_name.replace("-", " ").title()}{sentinel_suffix}',
        fontweight="bold",
    )

    # Set x-axis with evenly spaced categorical labels
    ax.set_xticks(x_positions)
    ax.set_xticklabels(dimensions)

    # Beautiful grid styling (already set in rcParams)
    ax.set_axisbelow(True)

    plt.tight_layout()

    if save_path:
        latency_path = save_path.replace(".png", "_latency.png")
        plt.savefig(latency_path, dpi=300, bbox_inches="tight")
        plt.savefig(latency_path.replace(".png", ".pdf"), dpi=300, bbox_inches="tight")
        logger.info(f"Latency plot saved to {latency_path}")

    return fig, ax


def plot_latency_comparison(
    df_main: pd.DataFrame,
    df_compare: pd.DataFrame,
    task_name: str,
    main_label: str,
    compare_label: str,
    save_path: Optional[str] = None,
):
    """Create latency comparison plot with grouped bars."""
    setup_plot_style()

    # Calculate latency data for both datasets
    latency_main = (
        df_main.groupby("dimension")
        .agg({"duration": ["mean", "std", "count"]})
        .round(2)
    )
    latency_main.columns = ["mean_duration", "std_duration", "count"]
    latency_main = latency_main.reset_index()
    latency_main["mean_duration_min"] = latency_main["mean_duration"] / 60
    latency_main["std_duration_min"] = latency_main["std_duration"] / 60

    latency_compare = (
        df_compare.groupby("dimension")
        .agg({"duration": ["mean", "std", "count"]})
        .round(2)
    )
    latency_compare.columns = ["mean_duration", "std_duration", "count"]
    latency_compare = latency_compare.reset_index()
    latency_compare["mean_duration_min"] = latency_compare["mean_duration"] / 60
    latency_compare["std_duration_min"] = latency_compare["std_duration"] / 60

    fig, ax = plt.subplots(figsize=(12, 6))

    # Get common dimensions
    dimensions = sorted(
        set(latency_main["dimension"]) & set(latency_compare["dimension"])
    )

    # Prepare data for plotting
    main_latencies = []
    compare_latencies = []
    main_stds = []
    compare_stds = []

    for dim in dimensions:
        main_row = latency_main[latency_main["dimension"] == dim]
        compare_row = latency_compare[latency_compare["dimension"] == dim]

        main_latencies.append(
            main_row.iloc[0]["mean_duration_min"] if len(main_row) > 0 else 0
        )
        compare_latencies.append(
            compare_row.iloc[0]["mean_duration_min"] if len(compare_row) > 0 else 0
        )
        main_stds.append(
            main_row.iloc[0]["std_duration_min"] if len(main_row) > 0 else 0
        )
        compare_stds.append(
            compare_row.iloc[0]["std_duration_min"] if len(compare_row) > 0 else 0
        )

    # Create grouped bar chart
    x = np.arange(len(dimensions))
    width = 0.35

    bars1 = ax.bar(
        x - width / 2,
        main_latencies,
        width,
        yerr=main_stds,
        capsize=4,
        label=main_label,
        color="#B19FE8",
        alpha=0.85,
        edgecolor="#7B68C7",
        linewidth=1.5,
        error_kw={"color": "#5A4B7B", "linewidth": 1.5},
    )
    bars2 = ax.bar(
        x + width / 2,
        compare_latencies,
        width,
        yerr=compare_stds,
        capsize=4,
        label=compare_label,
        color="#7B68C7",
        alpha=0.85,
        edgecolor="#5A4B7B",
        linewidth=1.5,
        error_kw={"color": "#5A4B7B", "linewidth": 1.5},
    )

    # Add value labels on bars
    max_std = max(max(main_stds), max(compare_stds))
    for i, (bar1, bar2, lat1, lat2) in enumerate(
        zip(bars1, bars2, main_latencies, compare_latencies)
    ):
        height1 = bar1.get_height()
        height2 = bar2.get_height()

        ax.text(
            bar1.get_x() + bar1.get_width() / 2,
            height1 + max_std * 0.1,
            f"{lat1:.1f}m",
            ha="center",
            va="bottom",
            fontweight="bold",
            fontsize=10,
            color="#5A4B7B",
        )
        ax.text(
            bar2.get_x() + bar2.get_width() / 2,
            height2 + max_std * 0.1,
            f"{lat2:.1f}m",
            ha="center",
            va="bottom",
            fontweight="bold",
            fontsize=10,
            color="#5A4B7B",
        )

    ax.set_xlabel("Task Dimension", fontweight="bold")
    ax.set_ylabel("Average Duration (minutes)", fontweight="bold")
    ax.set_title(
        f'Duration Comparison: {task_name.replace("-", " ").title()}', fontweight="bold"
    )

    ax.set_xticks(x)
    ax.set_xticklabels(dimensions)
    ax.legend(fontsize=12, frameon=True, fancybox=True, shadow=True)
    ax.set_axisbelow(True)

    plt.tight_layout()

    if save_path:
        latency_path = save_path.replace(".png", "_latency_comparison.png")
        plt.savefig(latency_path, dpi=300, bbox_inches="tight")
        plt.savefig(latency_path.replace(".png", ".pdf"), dpi=300, bbox_inches="tight")
        logger.info(f"Latency comparison plot saved to {latency_path}")

    return fig, ax


def plot_cost_vs_dimension(
    df: pd.DataFrame,
    task_name: str,
    model: str,
    sentinel: bool = False,
    save_path: Optional[str] = None,
):
    """Create cost vs dimension plot."""
    setup_plot_style()

    # Calculate costs
    df["cost"] = df.apply(
        lambda row: calculate_cost(
            row["prompt_tokens"], row["completion_tokens"], model
        ),
        axis=1,
    )

    # Group by dimension and calculate mean cost
    cost_data = df.groupby("dimension").agg({"cost": ["mean", "std", "count"]}).round(4)

    # Flatten column names
    cost_data.columns = ["mean_cost", "std_cost", "count"]
    cost_data = cost_data.reset_index()

    fig, ax = plt.subplots(figsize=(10, 6))

    dimensions = cost_data["dimension"]
    mean_costs = cost_data["mean_cost"]
    std_costs = cost_data["std_cost"]

    # Create evenly spaced x positions (treat dimensions as categorical)
    x_positions = range(len(dimensions))

    # Create beautiful bar plot with error bars
    bars = ax.bar(
        x_positions,
        mean_costs,
        yerr=std_costs,
        capsize=6,
        color="#C5BFF0",
        alpha=0.85,
        edgecolor="#8A7CA8",
        linewidth=1.5,
        capstyle="round",
        error_kw={"color": "#5A4B7B", "linewidth": 2},
    )

    # Add elegant value labels on bars
    for i, (bar, cost) in enumerate(zip(bars, mean_costs)):
        height = bar.get_height()
        ax.text(
            i,
            height + max(std_costs) * 0.1,
            f"${cost:.3f}",
            ha="center",
            va="bottom",
            fontweight="bold",
            fontsize=12,
            color="#5A4B7B",
        )

    sentinel_suffix = " (With Sentinel)" if sentinel else " (Without Sentinel)"
    ax.set_xlabel("Task Dimension", fontweight="bold")
    ax.set_ylabel("Average Cost (USD)", fontweight="bold")
    ax.set_title(
        f'Task Cost vs Dimension: {task_name.replace("-", " ").title()}{sentinel_suffix} ({model})',
        fontweight="bold",
    )

    # Set x-axis with evenly spaced categorical labels
    ax.set_xticks(x_positions)
    ax.set_xticklabels(dimensions)

    # Format y-axis to show currency
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f"${x:.3f}"))

    # Beautiful grid styling (already set in rcParams)
    ax.set_axisbelow(True)

    plt.tight_layout()

    if save_path:
        cost_path = save_path.replace(".png", "_cost.png")
        plt.savefig(cost_path, dpi=300, bbox_inches="tight")
        plt.savefig(cost_path.replace(".png", ".pdf"), dpi=300, bbox_inches="tight")
        logger.info(f"Cost plot saved to {cost_path}")

    return fig, ax


def plot_cost_comparison(
    df_main: pd.DataFrame,
    df_compare: pd.DataFrame,
    task_name: str,
    model: str,
    main_label: str,
    compare_label: str,
    save_path: Optional[str] = None,
):
    """Create cost comparison plot with grouped bars."""
    setup_plot_style()

    # Calculate costs for both datasets
    df_main["cost"] = df_main.apply(
        lambda row: calculate_cost(
            row["prompt_tokens"], row["completion_tokens"], model
        ),
        axis=1,
    )
    df_compare["cost"] = df_compare.apply(
        lambda row: calculate_cost(
            row["prompt_tokens"], row["completion_tokens"], model
        ),
        axis=1,
    )

    # Group by dimension and calculate mean cost
    cost_main = (
        df_main.groupby("dimension").agg({"cost": ["mean", "std", "count"]}).round(4)
    )
    cost_main.columns = ["mean_cost", "std_cost", "count"]
    cost_main = cost_main.reset_index()

    cost_compare = (
        df_compare.groupby("dimension").agg({"cost": ["mean", "std", "count"]}).round(4)
    )
    cost_compare.columns = ["mean_cost", "std_cost", "count"]
    cost_compare = cost_compare.reset_index()

    fig, ax = plt.subplots(figsize=(12, 6))

    # Get common dimensions
    dimensions = sorted(set(cost_main["dimension"]) & set(cost_compare["dimension"]))

    # Prepare data for plotting
    main_costs = []
    compare_costs = []
    main_stds = []
    compare_stds = []

    for dim in dimensions:
        main_row = cost_main[cost_main["dimension"] == dim]
        compare_row = cost_compare[cost_compare["dimension"] == dim]

        main_costs.append(main_row.iloc[0]["mean_cost"] if len(main_row) > 0 else 0)
        compare_costs.append(
            compare_row.iloc[0]["mean_cost"] if len(compare_row) > 0 else 0
        )
        main_stds.append(main_row.iloc[0]["std_cost"] if len(main_row) > 0 else 0)
        compare_stds.append(
            compare_row.iloc[0]["std_cost"] if len(compare_row) > 0 else 0
        )

    # Create grouped bar chart
    x = np.arange(len(dimensions))
    width = 0.35

    bars1 = ax.bar(
        x - width / 2,
        main_costs,
        width,
        yerr=main_stds,
        capsize=4,
        label=main_label,
        color="#B19FE8",
        alpha=0.85,
        edgecolor="#7B68C7",
        linewidth=1.5,
        error_kw={"color": "#5A4B7B", "linewidth": 1.5},
    )
    bars2 = ax.bar(
        x + width / 2,
        compare_costs,
        width,
        yerr=compare_stds,
        capsize=4,
        label=compare_label,
        color="#7B68C7",
        alpha=0.85,
        edgecolor="#5A4B7B",
        linewidth=1.5,
        error_kw={"color": "#5A4B7B", "linewidth": 1.5},
    )

    # Add value labels on bars
    max_std = max(max(main_stds), max(compare_stds))
    for i, (bar1, bar2, cost1, cost2) in enumerate(
        zip(bars1, bars2, main_costs, compare_costs)
    ):
        height1 = bar1.get_height()
        height2 = bar2.get_height()

        ax.text(
            bar1.get_x() + bar1.get_width() / 2,
            height1 + max_std * 0.1,
            f"${cost1:.3f}",
            ha="center",
            va="bottom",
            fontweight="bold",
            fontsize=10,
            color="#5A4B7B",
        )
        ax.text(
            bar2.get_x() + bar2.get_width() / 2,
            height2 + max_std * 0.1,
            f"${cost2:.3f}",
            ha="center",
            va="bottom",
            fontweight="bold",
            fontsize=10,
            color="#5A4B7B",
        )

    ax.set_xlabel("Task Dimension", fontweight="bold")
    ax.set_ylabel("Average Cost (USD)", fontweight="bold")
    ax.set_title(
        f'Cost Comparison: {task_name.replace("-", " ").title()} ({model})',
        fontweight="bold",
    )

    ax.set_xticks(x)
    ax.set_xticklabels(dimensions)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f"${x:.3f}"))
    ax.legend(fontsize=12, frameon=True, fancybox=True, shadow=True)
    ax.set_axisbelow(True)

    plt.tight_layout()

    if save_path:
        cost_path = save_path.replace(".png", "_cost_comparison.png")
        plt.savefig(cost_path, dpi=300, bbox_inches="tight")
        plt.savefig(cost_path.replace(".png", ".pdf"), dpi=300, bbox_inches="tight")
        logger.info(f"Cost comparison plot saved to {cost_path}")

    return fig, ax


def create_combined_plot(
    df: pd.DataFrame,
    task_name: str,
    model: str,
    sentinel: bool = False,
    save_path: Optional[str] = None,
):
    """Create a combined plot with all three metrics."""
    setup_plot_style()

    # Calculate all metrics
    accuracy_data = analyze_accuracy(df)
    df["cost"] = df.apply(
        lambda row: calculate_cost(
            row["prompt_tokens"], row["completion_tokens"], model
        ),
        axis=1,
    )

    latency_data = df.groupby("dimension").agg({"duration": "mean"}).reset_index()
    latency_data["duration_min"] = latency_data["duration"] / 60

    cost_data = df.groupby("dimension").agg({"cost": "mean"}).reset_index()

    # Create beautiful subplots with nice spacing
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(20, 6))
    fig.patch.set_facecolor("white")

    # Plot 1: Accuracy
    dimensions = accuracy_data["dimension"]
    accuracy_rates = accuracy_data["accuracy_rate"] * 100

    # Format dimension labels based on task type
    if is_duration_task(task_name):
        dimension_labels = [format_time_dimension(dim) for dim in dimensions]
    else:
        dimension_labels = [str(dim) for dim in dimensions]

    # Create evenly spaced x positions for all plots
    x_positions = range(len(dimensions))

    bars1 = ax1.bar(
        x_positions,
        accuracy_rates,
        color="#B19FE8",
        alpha=0.85,
        edgecolor="#7B68C7",
        linewidth=1.5,
        capstyle="round",
    )
    for i, (bar, acc) in enumerate(zip(bars1, accuracy_rates)):
        height = bar.get_height()
        ax1.text(
            i,
            height + 1,
            f"{acc:.1f}%",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
            color="#5A4B7B",
        )

    ax1.set_xlabel("Task Dimension", fontweight="bold")
    ax1.set_ylabel("Success Rate (%)", fontweight="bold")
    ax1.set_title("Success Rate", fontweight="bold")
    ax1.set_ylim(0, 105)
    ax1.yaxis.set_major_formatter(PercentFormatter())
    ax1.set_xticks(x_positions)
    ax1.set_xticklabels(dimension_labels)
    ax1.set_axisbelow(True)

    # Plot 2: Latency
    latencies = latency_data["duration_min"]
    bars2 = ax2.bar(
        x_positions,
        latencies,
        color="#9D7FE0",
        alpha=0.85,
        edgecolor="#6A5ACD",
        linewidth=1.5,
        capstyle="round",
    )
    for i, (bar, lat) in enumerate(zip(bars2, latencies)):
        height = bar.get_height()
        ax2.text(
            i,
            height * 1.02,
            f"{lat:.1f}m",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
            color="#5A4B7B",
        )

    ax2.set_xlabel("Task Dimension", fontweight="bold")
    ax2.set_ylabel("Duration (minutes)", fontweight="bold")
    ax2.set_title("Task Duration", fontweight="bold")
    ax2.set_xticks(x_positions)
    ax2.set_xticklabels(dimension_labels)
    ax2.set_axisbelow(True)

    # Plot 3: Cost
    costs = cost_data["cost"]
    bars3 = ax3.bar(
        x_positions,
        costs,
        color="#C5BFF0",
        alpha=0.85,
        edgecolor="#8A7CA8",
        linewidth=1.5,
        capstyle="round",
    )
    for i, (bar, cost) in enumerate(zip(bars3, costs)):
        height = bar.get_height()
        ax3.text(
            i,
            height * 1.02,
            f"${cost:.3f}",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
            color="#5A4B7B",
        )

    ax3.set_xlabel("Task Dimension", fontweight="bold")
    ax3.set_ylabel("Cost (USD)", fontweight="bold")
    ax3.set_title(f"Cost ({model})", fontweight="bold")
    ax3.set_xticks(x_positions)
    ax3.set_xticklabels(dimension_labels)
    ax3.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f"${x:.3f}"))
    ax3.set_axisbelow(True)

    # Add elegant overall title
    sentinel_suffix = " (With Sentinel)" if sentinel else " (Without Sentinel)"
    fig.suptitle(
        f'Performance Analysis: {task_name.replace("-", " ").title()} Task{sentinel_suffix}',
        fontsize=22,
        fontweight="bold",
        y=1.05,
        color="black",
    )

    plt.tight_layout()

    if save_path:
        combined_path = save_path.replace(".png", "_combined.png")
        plt.savefig(combined_path, dpi=300, bbox_inches="tight")
        plt.savefig(combined_path.replace(".png", ".pdf"), dpi=300, bbox_inches="tight")
        logger.info(f"Combined plot saved to {combined_path}")

    return fig, (ax1, ax2, ax3)


def create_combined_comparison_plot(
    df_main: pd.DataFrame,
    df_compare: pd.DataFrame,
    task_name: str,
    model: str,
    main_label: str,
    compare_label: str,
    save_path: Optional[str] = None,
):
    """Create a combined comparison plot with all three metrics."""
    setup_plot_style()

    # Calculate all metrics for both datasets
    accuracy_main = analyze_accuracy(df_main)
    accuracy_compare = analyze_accuracy(df_compare)

    df_main["cost"] = df_main.apply(
        lambda row: calculate_cost(
            row["prompt_tokens"], row["completion_tokens"], model
        ),
        axis=1,
    )
    df_compare["cost"] = df_compare.apply(
        lambda row: calculate_cost(
            row["prompt_tokens"], row["completion_tokens"], model
        ),
        axis=1,
    )

    latency_main = df_main.groupby("dimension").agg({"duration": "mean"}).reset_index()
    latency_main["duration_min"] = latency_main["duration"] / 60

    latency_compare = (
        df_compare.groupby("dimension").agg({"duration": "mean"}).reset_index()
    )
    latency_compare["duration_min"] = latency_compare["duration"] / 60

    cost_main = df_main.groupby("dimension").agg({"cost": "mean"}).reset_index()

    cost_compare = df_compare.groupby("dimension").agg({"cost": "mean"}).reset_index()

    # Get common dimensions
    dimensions = sorted(
        set(accuracy_main["dimension"]) & set(accuracy_compare["dimension"])
    )

    # Format dimension labels based on task type
    if is_duration_task(task_name):
        dimension_labels = [format_time_dimension(dim) for dim in dimensions]
    else:
        dimension_labels = [str(dim) for dim in dimensions]

    # Create beautiful subplots with nice spacing
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(24, 6))
    fig.patch.set_facecolor("white")

    # Prepare data for all plots
    x = np.arange(len(dimensions))
    width = 0.35

    # Plot 1: Accuracy Comparison
    main_acc_rates = []
    compare_acc_rates = []

    for dim in dimensions:
        main_row = accuracy_main[accuracy_main["dimension"] == dim]
        compare_row = accuracy_compare[accuracy_compare["dimension"] == dim]

        main_acc_rates.append(
            main_row.iloc[0]["accuracy_rate"] * 100 if len(main_row) > 0 else 0
        )
        compare_acc_rates.append(
            compare_row.iloc[0]["accuracy_rate"] * 100 if len(compare_row) > 0 else 0
        )

    bars1_1 = ax1.bar(
        x - width / 2,
        main_acc_rates,
        width,
        label=main_label,
        color="#B19FE8",
        alpha=0.85,
        edgecolor="#7B68C7",
        linewidth=1.5,
    )
    bars1_2 = ax1.bar(
        x + width / 2,
        compare_acc_rates,
        width,
        label=compare_label,
        color="#7B68C7",
        alpha=0.85,
        edgecolor="#5A4B7B",
        linewidth=1.5,
    )

    for i, (bar1, bar2, acc1, acc2) in enumerate(
        zip(bars1_1, bars1_2, main_acc_rates, compare_acc_rates)
    ):
        height1 = bar1.get_height()
        height2 = bar2.get_height()
        ax1.text(
            bar1.get_x() + bar1.get_width() / 2,
            height1 + 1,
            f"{acc1:.1f}%",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
            color="#5A4B7B",
        )
        ax1.text(
            bar2.get_x() + bar2.get_width() / 2,
            height2 + 1,
            f"{acc2:.1f}%",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
            color="#5A4B7B",
        )

    ax1.set_xlabel("Task Dimension", fontweight="bold")
    ax1.set_ylabel("Success Rate (%)", fontweight="bold")
    ax1.set_title("Success Rate", fontweight="bold")
    ax1.set_ylim(0, 105)
    ax1.yaxis.set_major_formatter(PercentFormatter())
    ax1.set_xticks(x)
    ax1.set_xticklabels(dimension_labels)
    ax1.legend(fontsize=10, frameon=True, fancybox=True, shadow=True)
    ax1.set_axisbelow(True)

    # Plot 2: Latency Comparison
    main_latencies = []
    compare_latencies = []

    for dim in dimensions:
        main_row = latency_main[latency_main["dimension"] == dim]
        compare_row = latency_compare[latency_compare["dimension"] == dim]

        main_latencies.append(
            main_row.iloc[0]["duration_min"] if len(main_row) > 0 else 0
        )
        compare_latencies.append(
            compare_row.iloc[0]["duration_min"] if len(compare_row) > 0 else 0
        )

    bars2_1 = ax2.bar(
        x - width / 2,
        main_latencies,
        width,
        label=main_label,
        color="#B19FE8",
        alpha=0.85,
        edgecolor="#7B68C7",
        linewidth=1.5,
    )
    bars2_2 = ax2.bar(
        x + width / 2,
        compare_latencies,
        width,
        label=compare_label,
        color="#7B68C7",
        alpha=0.85,
        edgecolor="#5A4B7B",
        linewidth=1.5,
    )

    for i, (bar1, bar2, lat1, lat2) in enumerate(
        zip(bars2_1, bars2_2, main_latencies, compare_latencies)
    ):
        height1 = bar1.get_height()
        height2 = bar2.get_height()
        ax2.text(
            bar1.get_x() + bar1.get_width() / 2,
            height1 * 1.02,
            f"{lat1:.1f}m",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
            color="#5A4B7B",
        )
        ax2.text(
            bar2.get_x() + bar2.get_width() / 2,
            height2 * 1.02,
            f"{lat2:.1f}m",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
            color="#5A4B7B",
        )

    ax2.set_xlabel("Task Dimension", fontweight="bold")
    ax2.set_ylabel("Duration (minutes)", fontweight="bold")
    ax2.set_title("Task Duration", fontweight="bold")
    ax2.set_xticks(x)
    ax2.set_xticklabels(dimension_labels)
    ax2.legend(fontsize=10, frameon=True, fancybox=True, shadow=True)
    ax2.set_axisbelow(True)

    # Plot 3: Cost Comparison
    main_costs = []
    compare_costs = []

    for dim in dimensions:
        main_row = cost_main[cost_main["dimension"] == dim]
        compare_row = cost_compare[cost_compare["dimension"] == dim]

        main_costs.append(main_row.iloc[0]["cost"] if len(main_row) > 0 else 0)
        compare_costs.append(compare_row.iloc[0]["cost"] if len(compare_row) > 0 else 0)

    bars3_1 = ax3.bar(
        x - width / 2,
        main_costs,
        width,
        label=main_label,
        color="#B19FE8",
        alpha=0.85,
        edgecolor="#7B68C7",
        linewidth=1.5,
    )
    bars3_2 = ax3.bar(
        x + width / 2,
        compare_costs,
        width,
        label=compare_label,
        color="#7B68C7",
        alpha=0.85,
        edgecolor="#5A4B7B",
        linewidth=1.5,
    )

    for i, (bar1, bar2, cost1, cost2) in enumerate(
        zip(bars3_1, bars3_2, main_costs, compare_costs)
    ):
        height1 = bar1.get_height()
        height2 = bar2.get_height()
        ax3.text(
            bar1.get_x() + bar1.get_width() / 2,
            height1 * 1.02,
            f"${cost1:.3f}",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
            color="#5A4B7B",
        )
        ax3.text(
            bar2.get_x() + bar2.get_width() / 2,
            height2 * 1.02,
            f"${cost2:.3f}",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
            color="#5A4B7B",
        )

    ax3.set_xlabel("Task Dimension", fontweight="bold")
    ax3.set_ylabel("Cost (USD)", fontweight="bold")
    ax3.set_title(f"Cost ({model})", fontweight="bold")
    ax3.set_xticks(x)
    ax3.set_xticklabels(dimension_labels)
    ax3.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f"${x:.3f}"))
    ax3.legend(fontsize=10, frameon=True, fancybox=True, shadow=True)
    ax3.set_axisbelow(True)

    # Add elegant overall title
    fig.suptitle(
        f'Performance Comparison: {task_name.replace("-", " ").title()} Task',
        fontsize=22,
        fontweight="bold",
        y=1.05,
        color="black",
    )

    plt.tight_layout()

    if save_path:
        combined_path = save_path.replace(".png", "_combined_comparison.png")
        plt.savefig(combined_path, dpi=300, bbox_inches="tight")
        plt.savefig(combined_path.replace(".png", ".pdf"), dpi=300, bbox_inches="tight")
        logger.info(f"Combined comparison plot saved to {combined_path}")

    return fig, (ax1, ax2, ax3)


def print_summary_statistics(
    df: pd.DataFrame, task_name: str, model: str, sentinel: bool = False
):
    """Print comprehensive summary statistics."""
    sentinel_suffix = " (With Sentinel)" if sentinel else " (Without Sentinel)"
    print("\n" + "=" * 80)
    print(f"SUMMARY STATISTICS: {task_name.replace('-', ' ').title()}{sentinel_suffix}")
    print("=" * 80)

    # Calculate metrics
    accuracy_data = analyze_accuracy(df)
    df["cost"] = df.apply(
        lambda row: calculate_cost(
            row["prompt_tokens"], row["completion_tokens"], model
        ),
        axis=1,
    )

    print(f"\nDimensions analyzed: {sorted(df['dimension'].unique())}")
    print(f"Total task runs: {len(df)}")
    print(f"Model used for cost calculation: {model}")

    print(
        f"\n{'Dimension':<10} {'Success Rate':<12} {'Avg Duration':<15} {'Avg Cost':<10} {'Total Tasks':<12}"
    )
    print("-" * 65)

    for dim in sorted(df["dimension"].unique()):
        dim_data = df[df["dimension"] == dim]
        acc_row = accuracy_data[accuracy_data["dimension"] == dim].iloc[0]

        success_rate = acc_row["accuracy_rate"] * 100
        avg_duration = dim_data["duration"].mean() / 60  # Convert to minutes
        avg_cost = dim_data["cost"].mean()
        total_tasks = acc_row["total_tasks"]

        print(
            f"{dim:<10} {success_rate:<11.1f}% {avg_duration:<14.1f}m ${avg_cost:<9.3f} {total_tasks:<12}"
        )

    print("\nOverall Statistics:")
    print(f"  Average accuracy: {accuracy_data['accuracy_rate'].mean() * 100:.1f}%")
    print(f"  Average duration: {df['duration'].mean() / 60:.1f} minutes")
    print(f"  Average cost per task: ${df['cost'].mean():.3f}")
    print(f"  Total cost for all runs: ${df['cost'].sum():.3f}")
    print(f"  Total tokens used: {df['total_tokens'].sum():,}")

    # Show score distribution if available
    if "score" in df.columns and df["score"].notna().sum() > 0:
        perfect_scores = (df["score"] == 1.0).sum()
        partial_scores = ((df["score"] > 0) & (df["score"] < 1.0)).sum()
        zero_scores = (df["score"] == 0.0).sum()
        print(
            f"  Score distribution: {perfect_scores} perfect (1.0), {partial_scores} partial (0-1), {zero_scores} failed (0.0)"
        )


def print_comparison_summary(
    df_main: pd.DataFrame,
    df_compare: pd.DataFrame,
    task_name: str,
    model: str,
    main_label: str,
    compare_label: str,
):
    """Print comprehensive comparison summary statistics."""
    print("\n" + "=" * 100)
    print(f"COMPARISON SUMMARY: {task_name.replace('-', ' ').title()}")
    print(f"{main_label} vs {compare_label}")
    print("=" * 100)

    # Calculate metrics for both datasets
    accuracy_main = analyze_accuracy(df_main)
    accuracy_compare = analyze_accuracy(df_compare)

    df_main["cost"] = df_main.apply(
        lambda row: calculate_cost(
            row["prompt_tokens"], row["completion_tokens"], model
        ),
        axis=1,
    )
    df_compare["cost"] = df_compare.apply(
        lambda row: calculate_cost(
            row["prompt_tokens"], row["completion_tokens"], model
        ),
        axis=1,
    )

    # Get common dimensions
    dimensions = sorted(
        set(df_main["dimension"].unique()) & set(df_compare["dimension"].unique())
    )

    print(f"\nDimensions analyzed: {dimensions}")
    print(
        f"Total runs: {main_label}: {len(df_main)}, {compare_label}: {len(df_compare)}"
    )
    print(f"Model used for cost calculation: {model}")

    print(
        f"\n{'Dimension':<10} {'Metric':<15} {main_label:<20} {compare_label:<20} {'Difference':<15}"
    )
    print("-" * 85)

    for dim in dimensions:
        dim_main = df_main[df_main["dimension"] == dim]
        dim_compare = df_compare[df_compare["dimension"] == dim]

        if len(dim_main) == 0 or len(dim_compare) == 0:
            continue

        # Accuracy
        acc_main_row = accuracy_main[accuracy_main["dimension"] == dim]
        acc_compare_row = accuracy_compare[accuracy_compare["dimension"] == dim]

        if len(acc_main_row) > 0 and len(acc_compare_row) > 0:
            acc_main = acc_main_row.iloc[0]["accuracy_rate"] * 100
            acc_compare = acc_compare_row.iloc[0]["accuracy_rate"] * 100
            acc_diff = acc_main - acc_compare

            print(
                f"{dim:<10} {'Success Rate':<15} {acc_main:<19.1f}% {acc_compare:<19.1f}% {acc_diff:+.1f}%"
            )

        # Duration
        dur_main = dim_main["duration"].mean() / 60
        dur_compare = dim_compare["duration"].mean() / 60
        dur_diff = dur_main - dur_compare

        print(
            f"{'':<10} {'Duration':<15} {dur_main:<19.1f}m {dur_compare:<19.1f}m {dur_diff:+.1f}m"
        )

        # Cost
        cost_main = dim_main["cost"].mean()
        cost_compare = dim_compare["cost"].mean()
        cost_diff = cost_main - cost_compare

        print(
            f"{'':<10} {'Cost':<15} ${cost_main:<18.3f} ${cost_compare:<18.3f} ${cost_diff:+.3f}"
        )
        print("-" * 85)

    # Overall comparison
    print("\nOverall Performance Comparison:")
    print(f"{'Metric':<20} {main_label:<20} {compare_label:<20} {'Difference':<15}")
    print("-" * 80)

    # Overall accuracy
    overall_acc_main = accuracy_main["accuracy_rate"].mean() * 100
    overall_acc_compare = accuracy_compare["accuracy_rate"].mean() * 100
    overall_acc_diff = overall_acc_main - overall_acc_compare
    print(
        f"{'Avg Success Rate':<20} {overall_acc_main:<19.1f}% {overall_acc_compare:<19.1f}% {overall_acc_diff:+.1f}%"
    )

    # Overall duration
    overall_dur_main = df_main["duration"].mean() / 60
    overall_dur_compare = df_compare["duration"].mean() / 60
    overall_dur_diff = overall_dur_main - overall_dur_compare
    print(
        f"{'Avg Duration':<20} {overall_dur_main:<19.1f}m {overall_dur_compare:<19.1f}m {overall_dur_diff:+.1f}m"
    )

    # Overall cost
    overall_cost_main = df_main["cost"].mean()
    overall_cost_compare = df_compare["cost"].mean()
    overall_cost_diff = overall_cost_main - overall_cost_compare
    print(
        f"{'Avg Cost':<20} ${overall_cost_main:<18.3f} ${overall_cost_compare:<18.3f} ${overall_cost_diff:+.3f}"
    )

    # Total costs
    total_cost_main = df_main["cost"].sum()
    total_cost_compare = df_compare["cost"].sum()
    total_cost_diff = total_cost_main - total_cost_compare
    print(
        f"{'Total Cost':<20} ${total_cost_main:<18.3f} ${total_cost_compare:<18.3f} ${total_cost_diff:+.3f}"
    )

    # Total tokens
    total_tokens_main = df_main["total_tokens"].sum()
    total_tokens_compare = df_compare["total_tokens"].sum()
    print(
        f"{'Total Tokens':<20} {total_tokens_main:<19,} {total_tokens_compare:<19,} {total_tokens_main - total_tokens_compare:+,}"
    )

    # Performance summary
    print("\n🏆 Performance Winner Summary:")
    if overall_acc_diff > 0:
        print(
            f"   Accuracy: {main_label} wins by {overall_acc_diff:.1f} percentage points"
        )
    elif overall_acc_diff < 0:
        print(
            f"   Accuracy: {compare_label} wins by {abs(overall_acc_diff):.1f} percentage points"
        )
    else:
        print("   Accuracy: Tie")

    if overall_dur_diff < 0:
        print(
            f"   Speed: {main_label} wins (faster by {abs(overall_dur_diff):.1f} minutes)"
        )
    elif overall_dur_diff > 0:
        print(
            f"   Speed: {compare_label} wins (faster by {overall_dur_diff:.1f} minutes)"
        )
    else:
        print("   Speed: Tie")

    if overall_cost_diff < 0:
        print(
            f"   Cost Efficiency: {main_label} wins (cheaper by ${abs(overall_cost_diff):.3f})"
        )
    elif overall_cost_diff > 0:
        print(
            f"   Cost Efficiency: {compare_label} wins (cheaper by ${overall_cost_diff:.3f})"
        )
    else:
        print("   Cost Efficiency: Tie")


def main(
    run_dir: Annotated[
        str,
        typer.Option(
            help="Path to run directory (e.g., runs/MagenticUI/SentinelBench/test/4000)"
        ),
    ],
    task_name: Annotated[
        str, typer.Option(help="Name of the task to analyze (e.g., animal-mover-easy)")
    ],
    model: Annotated[str, typer.Option(help="Model name for cost calculation")],
    output_dir: Annotated[str, typer.Option(help="Directory to save plots")] = "plots",
    output_prefix: Annotated[
        Optional[str], typer.Option(help="Prefix for output files (default: task-name)")
    ] = None,
    combined: Annotated[
        bool, typer.Option(help="Create combined plot with all metrics")
    ] = False,
    save_csv: Annotated[
        bool, typer.Option(help="Save processed data to CSV file")
    ] = False,
    sentinel: Annotated[
        bool, typer.Option(help="Add sentinel suffix to plots and filenames")
    ] = False,
    compare_with: Annotated[
        Optional[str], typer.Option(help="Path to second run directory for comparison")
    ] = None,
    main_label: Annotated[
        str, typer.Option(help="Label for main run in comparison mode")
    ] = "Run 1",
    compare_label: Annotated[
        str, typer.Option(help="Label for comparison run")
    ] = "Run 2",
    intersection_only: Annotated[
        bool,
        typer.Option(
            help="Only include task+dimension combinations that exist in both directories"
        ),
    ] = False,
    union_fill: Annotated[
        bool,
        typer.Option(
            help="Include all task+dimension combinations from both directories, filling missing ones with default values"
        ),
    ] = False,
):
    # Validate model choice
    if model not in MODEL_PRICING:
        typer.echo(
            f"❌ Model must be one of: {', '.join(MODEL_PRICING.keys())}", err=True
        )
        raise typer.Exit(1)

    # Validate intersection/union flags
    if intersection_only and union_fill:
        typer.echo(
            "❌ Cannot use both --intersection-only and --union-fill flags simultaneously",
            err=True,
        )
        raise typer.Exit(1)

    if (intersection_only or union_fill) and compare_with is None:
        typer.echo(
            "❌ --intersection-only and --union-fill flags require --compare-with to be specified",
            err=True,
        )
        raise typer.Exit(1)

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Determine if we're in comparison mode
    is_comparison = compare_with is not None

    # Set default output prefix
    if output_prefix is None:
        base_prefix = task_name.replace("/", "_").replace(" ", "_")
        if is_comparison:
            output_prefix = f"{base_prefix}-comparison"
        else:
            output_prefix = (
                f"{base_prefix}-with-sentinel"
                if sentinel
                else f"{base_prefix}-without-sentinel"
            )

    try:
        if is_comparison:
            # Comparison mode: load data from both directories
            logger.info(
                f"Loading data for comparison: '{task_name}' from {run_dir} vs {compare_with}"
            )
            df_main, df_compare = load_comparison_data(
                run_dir,
                compare_with,
                task_name,
                intersection_only,
                union_fill,
                main_label,
                compare_label,
            )

            if len(df_main) == 0 or len(df_compare) == 0:
                logger.error("No data found in one or both directories. Exiting.")
                return

            # Add labels to distinguish the datasets
            df_main["run_type"] = main_label
            df_compare["run_type"] = compare_label

            # Save to CSV if requested
            if save_csv:
                # Add cost column before saving
                df_main["cost"] = df_main.apply(
                    lambda row: calculate_cost(
                        row["prompt_tokens"], row["completion_tokens"], model
                    ),
                    axis=1,
                )
                df_compare["cost"] = df_compare.apply(
                    lambda row: calculate_cost(
                        row["prompt_tokens"], row["completion_tokens"], model
                    ),
                    axis=1,
                )

                csv_path_main = os.path.join(
                    output_dir,
                    f"{output_prefix}_{main_label.lower().replace(' ', '_')}_analysis.csv",
                )
                csv_path_compare = os.path.join(
                    output_dir,
                    f"{output_prefix}_{compare_label.lower().replace(' ', '_')}_analysis.csv",
                )
                df_main.to_csv(csv_path_main, index=False)
                df_compare.to_csv(csv_path_compare, index=False)
                logger.info(f"Data saved to {csv_path_main} and {csv_path_compare}")

            # Create base path for plots
            base_path = os.path.join(output_dir, f"{output_prefix}.png")

            if combined:
                # Create combined comparison plot
                logger.info("Creating combined comparison analysis plot...")
                create_combined_comparison_plot(
                    df_main,
                    df_compare,
                    task_name,
                    model,
                    main_label,
                    compare_label,
                    base_path,
                )
            else:
                # Create individual comparison plots
                logger.info("Creating accuracy comparison plot...")
                plot_accuracy_comparison(
                    df_main, df_compare, task_name, main_label, compare_label, base_path
                )

                logger.info("Creating latency comparison plot...")
                plot_latency_comparison(
                    df_main, df_compare, task_name, main_label, compare_label, base_path
                )

                logger.info("Creating cost comparison plot...")
                plot_cost_comparison(
                    df_main,
                    df_compare,
                    task_name,
                    model,
                    main_label,
                    compare_label,
                    base_path,
                )

            # Print comparison summary statistics
            print_comparison_summary(
                df_main, df_compare, task_name, model, main_label, compare_label
            )

        else:
            # Single directory mode (existing functionality)
            logger.info(f"Loading data for task '{task_name}' from {run_dir}")
            df = load_task_data(run_dir, task_name)

            if len(df) == 0:
                logger.error("No data found. Exiting.")
                return

            # Save to CSV if requested
            if save_csv:
                # Add cost column before saving
                df["cost"] = df.apply(
                    lambda row: calculate_cost(
                        row["prompt_tokens"], row["completion_tokens"], model
                    ),
                    axis=1,
                )

                csv_path = os.path.join(output_dir, f"{output_prefix}_analysis.csv")
                df.to_csv(csv_path, index=False)
                logger.info(f"Data saved to {csv_path}")

            # Create base path for plots
            base_path = os.path.join(output_dir, f"{output_prefix}.png")

            if combined:
                # Create combined plot
                logger.info("Creating combined analysis plot...")
                create_combined_plot(df, task_name, model, sentinel, base_path)
            else:
                # Create individual plots
                logger.info("Creating accuracy plot...")
                plot_accuracy_vs_dimension(df, task_name, sentinel, base_path)

                logger.info("Creating latency plot...")
                plot_latency_vs_dimension(df, task_name, sentinel, base_path)

                logger.info("Creating cost plot...")
                plot_cost_vs_dimension(df, task_name, model, sentinel, base_path)

            # Print summary statistics
            print_summary_statistics(df, task_name, model, sentinel)

        logger.info(f"Analysis complete! Plots saved to {output_dir}/")

    except Exception as e:
        logger.error(f"Error during analysis: {e}")
        raise


if __name__ == "__main__":
    typer.run(main)
