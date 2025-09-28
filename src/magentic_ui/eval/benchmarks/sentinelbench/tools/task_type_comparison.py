#!/usr/bin/env python3
# type: ignore[reportUnknownMemberType,reportUnknownVariableType,reportMissingTypeStubs]
"""
Analyze SentinelBench performance by task type (duration vs count based).
Creates combined plots showing accuracy, latency, and cost scaling averaged across task types.

Usage:
    python task_type_comparison.py --sentinel-csv plots/FINAL/all_tasks_with_sentinel.csv \
                                 --non-sentinel-csv plots/FINAL/all_tasks_without_sentinel.csv \
                                 --model gpt-5-mini \
                                 --output-dir plots/task_types
"""

from __future__ import annotations

import matplotlib.pyplot as plt  # type: ignore
from matplotlib.ticker import PercentFormatter, FuncFormatter  # type: ignore
from matplotlib.figure import Figure  # type: ignore
from matplotlib.axes import Axes  # type: ignore

try:
    from matplotlib.pyplot import cycler  # type: ignore
except ImportError:
    from cycler import cycler  # type: ignore

import pandas as pd
from pandas import DataFrame
import numpy as np
import argparse
import os
from typing import Optional, Dict, List, Set, Tuple, cast
import logging
import sys
from pathlib import Path

# Import task variants from centralized configuration
sys.path.append(str(Path(__file__).parent.parent))
try:
    from task_variants import (  # type: ignore
        SENTINELBENCH_TASK_VARIANTS,
        MODEL_PRICING,
        DURATION_TASK_PATTERNS,
        COUNT_TASK_PATTERNS,
    )
except ImportError:
    # Fallback if import fails
    _SENTINELBENCH_TASK_VARIANTS: Dict[str, List[int]] = {}
    _MODEL_PRICING: Dict[str, Dict[str, float]] = {}
    _DURATION_TASK_PATTERNS: List[str] = []
    _COUNT_TASK_PATTERNS: List[str] = []
    globals().update(
        {
            "SENTINELBENCH_TASK_VARIANTS": _SENTINELBENCH_TASK_VARIANTS,
            "MODEL_PRICING": _MODEL_PRICING,
            "DURATION_TASK_PATTERNS": _DURATION_TASK_PATTERNS,
            "COUNT_TASK_PATTERNS": _COUNT_TASK_PATTERNS,
        }
    )

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Extract expected dimensions from task_variants.py
def get_expected_dimensions() -> Tuple[List[int], List[int]]:
    """Extract expected dimensions from task variants, organized by task type."""
    duration_dims: Set[int] = set()
    count_dims: Set[int] = set()

    for task_name, dims in SENTINELBENCH_TASK_VARIANTS.items():
        # Determine task type based on patterns
        if any(pattern in task_name for pattern in DURATION_TASK_PATTERNS):
            duration_dims.update(dims)
        elif any(pattern in task_name for pattern in COUNT_TASK_PATTERNS):
            count_dims.update(dims)

    return sorted(duration_dims), sorted(count_dims)


_dimensions_result = get_expected_dimensions()
DURATION_DIMENSIONS: List[int] = _dimensions_result[0]
COUNT_DIMENSIONS: List[int] = _dimensions_result[1]


def setup_plot_style():
    """Set up beautiful, paper-ready plot styling with light purple cartoonish theme (from analyze_dimensions.py)."""
    # Use a clean, modern style as base
    plt.style.use("default")  # type: ignore

    # Font settings for NeurIPS-style academic papers
    plt.rcParams["font.family"] = "serif"  # type: ignore
    plt.rcParams["font.serif"] = [  # type: ignore
        "Times",
        "Computer Modern Roman",
        "CMU Serif",
        "Liberation Serif",
        "DejaVu Serif",
        "serif",
    ]
    plt.rcParams["font.size"] = 14  # type: ignore
    plt.rcParams["axes.labelsize"] = 16  # type: ignore
    plt.rcParams["axes.titlesize"] = 18  # type: ignore
    plt.rcParams["xtick.labelsize"] = 13  # type: ignore
    plt.rcParams["ytick.labelsize"] = 13  # type: ignore
    plt.rcParams["legend.fontsize"] = 14  # type: ignore
    plt.rcParams["figure.titlesize"] = 20  # type: ignore

    # High-quality settings for publication
    plt.rcParams["figure.dpi"] = 150  # type: ignore
    plt.rcParams["savefig.dpi"] = 300  # type: ignore
    plt.rcParams["savefig.bbox"] = "tight"  # type: ignore
    plt.rcParams["savefig.pad_inches"] = 0.1  # type: ignore

    # Beautiful color scheme
    plt.rcParams["axes.prop_cycle"] = cycler(  # type: ignore
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
    plt.rcParams["axes.spines.top"] = False  # type: ignore
    plt.rcParams["axes.spines.right"] = False  # type: ignore
    plt.rcParams["axes.spines.left"] = True  # type: ignore
    plt.rcParams["axes.spines.bottom"] = True  # type: ignore
    plt.rcParams["axes.linewidth"] = 1.2  # type: ignore
    plt.rcParams["axes.edgecolor"] = "#666666"  # type: ignore

    # Grid styling
    plt.rcParams["axes.grid"] = True  # type: ignore
    plt.rcParams["grid.alpha"] = 0.3  # type: ignore
    plt.rcParams["grid.linewidth"] = 0.8  # type: ignore
    plt.rcParams["grid.color"] = "#CCCCCC"  # type: ignore

    # Background colors
    plt.rcParams["figure.facecolor"] = "white"  # type: ignore
    plt.rcParams["axes.facecolor"] = "#FEFEFE"  # type: ignore


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


def filter_tasks_by_type(df: DataFrame, task_type: str) -> DataFrame:
    """Filter tasks by type (duration or count)."""
    if task_type == "duration":
        patterns = DURATION_TASK_PATTERNS
        valid_dimensions = DURATION_DIMENSIONS
    elif task_type == "count":
        patterns = COUNT_TASK_PATTERNS
        valid_dimensions = COUNT_DIMENSIONS
    else:
        raise ValueError(
            f"Invalid task_type: {task_type}. Must be 'duration' or 'count'."
        )

    # Filter by task name patterns
    mask = df["task_id"].str.contains("|".join(patterns), na=False)  # type: ignore
    filtered_df = df[mask].copy()  # type: ignore

    # Filter by valid dimensions for this task type
    filtered_df = filtered_df[filtered_df["dimension"].isin(valid_dimensions)]  # type: ignore

    logger.info(
        f"Filtered {task_type} tasks: {len(filtered_df)} rows from {filtered_df['task_id'].nunique()} unique tasks"
    )
    logger.info(f"Task IDs found: {sorted(filtered_df['task_id'].unique())}")
    logger.info(f"Dimensions found: {sorted(filtered_df['dimension'].unique())}")

    return filtered_df


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


def aggregate_by_dimension(df: DataFrame, model: str) -> DataFrame:
    """Aggregate metrics by dimension across all tasks."""
    # Add cost column
    df_copy = df.copy()
    df_copy["cost"] = df_copy.apply(
        lambda row: calculate_cost(
            int(row["prompt_tokens"]), int(row["completion_tokens"]), model
        ),
        axis=1,
    )
    df = df_copy

    # Group by dimension and calculate mean metrics
    aggregated = (
        df.groupby("dimension")
        .agg(
            {
                "score": "mean",  # Average accuracy across all tasks
                "duration": "mean",  # Average duration across all tasks
                "cost": "mean",  # Average cost across all tasks
                "task_id": "nunique",  # Number of unique tasks (for verification)
            }
        )
        .reset_index()
    )

    # Convert score to percentage
    aggregated["accuracy_rate"] = aggregated["score"] * 100

    # Convert duration to minutes
    aggregated["duration_min"] = aggregated["duration"] / 60

    return aggregated


def create_combined_comparison_plot(
    df_main: DataFrame,
    df_compare: DataFrame,
    task_type: str,
    model: str,
    main_label: str,
    compare_label: str,
    save_path: Optional[str] = None,
) -> Tuple[Figure, Tuple[Axes, Axes, Axes]]:
    """Create a combined comparison plot with all three metrics (same style as analyze_dimensions.py)."""
    setup_plot_style()

    # Aggregate data for both datasets
    agg_main = aggregate_by_dimension(df_main, model)
    agg_compare = aggregate_by_dimension(df_compare, model)

    # Get common dimensions
    dimensions_list = sorted(set(agg_main["dimension"]) & set(agg_compare["dimension"]))
    dimensions = [int(d) for d in dimensions_list]

    # Format dimension labels based on task type
    if task_type == "duration":
        dimension_labels = [format_time_dimension(dim) for dim in dimensions]
    else:
        dimension_labels = [str(dim) for dim in dimensions]

    # Create beautiful subplots with nice spacing
    fig, axes = plt.subplots(1, 3, figsize=(24, 6))  # type: ignore
    ax1, ax2, ax3 = cast(Tuple[Axes, Axes, Axes], axes)
    fig.patch.set_facecolor("white")  # type: ignore

    # Prepare data for all plots
    x = np.arange(len(dimensions))
    width = 0.35

    # Plot 1: Accuracy Comparison
    main_acc_rates: List[float] = []
    compare_acc_rates: List[float] = []

    for dim in dimensions:
        main_row = agg_main[agg_main["dimension"] == dim]
        compare_row = agg_compare[agg_compare["dimension"] == dim]

        main_acc_rates.append(
            float(main_row.iloc[0]["accuracy_rate"]) if len(main_row) > 0 else 0.0
        )
        compare_acc_rates.append(
            float(compare_row.iloc[0]["accuracy_rate"]) if len(compare_row) > 0 else 0.0
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

    for _, (bar1, bar2, acc1, acc2) in enumerate(
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
    ax1.yaxis.set_major_formatter(PercentFormatter())  # type: ignore
    ax1.set_xticks(x)
    ax1.set_xticklabels(dimension_labels)
    ax1.legend(fontsize=10, frameon=True, fancybox=True, shadow=True)
    ax1.set_axisbelow(True)

    # Plot 2: Latency Comparison
    main_latencies: List[float] = []
    compare_latencies: List[float] = []

    for dim in dimensions:
        main_row = agg_main[agg_main["dimension"] == dim]
        compare_row = agg_compare[agg_compare["dimension"] == dim]

        main_latencies.append(
            float(main_row.iloc[0]["duration_min"]) if len(main_row) > 0 else 0.0
        )
        compare_latencies.append(
            float(compare_row.iloc[0]["duration_min"]) if len(compare_row) > 0 else 0.0
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

    for _, (bar1, bar2, lat1, lat2) in enumerate(
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
    main_costs: List[float] = []
    compare_costs: List[float] = []

    for dim in dimensions:
        main_row = agg_main[agg_main["dimension"] == dim]
        compare_row = agg_compare[agg_compare["dimension"] == dim]

        main_costs.append(float(main_row.iloc[0]["cost"]) if len(main_row) > 0 else 0.0)
        compare_costs.append(
            float(compare_row.iloc[0]["cost"]) if len(compare_row) > 0 else 0.0
        )

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

    for _, (bar1, bar2, cost1, cost2) in enumerate(
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
    ax3.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"${x:.3f}"))  # type: ignore
    ax3.legend(fontsize=10, frameon=True, fancybox=True, shadow=True)
    ax3.set_axisbelow(True)

    # Add elegant overall title
    if task_type == "duration":
        title = "Performance Comparison: Time-Based Tasks (Duration)"
    else:
        title = "Performance Comparison: Repetition-Based Tasks (Count)"

    fig.suptitle(title, fontsize=22, fontweight="bold", y=1.05, color="black")  # type: ignore

    plt.tight_layout()  # type: ignore

    if save_path:
        combined_path = save_path.replace(
            ".png", f"_{task_type}_tasks_combined_comparison.png"
        )
        plt.savefig(combined_path, dpi=300, bbox_inches="tight")  # type: ignore
        plt.savefig(combined_path.replace(".png", ".pdf"), dpi=300, bbox_inches="tight")  # type: ignore
        logger.info(f"Combined {task_type} comparison plot saved to {combined_path}")

    return fig, (ax1, ax2, ax3)


def print_summary_statistics(
    df_main: DataFrame,
    df_compare: DataFrame,
    task_type: str,
    model: str,
    main_label: str,
    compare_label: str,
) -> None:
    """Print comprehensive comparison summary statistics."""
    print("\n" + "=" * 100)
    print(f"TASK TYPE COMPARISON: {task_type.title()}-Based Tasks")
    print(f"{main_label} vs {compare_label}")
    print("=" * 100)

    # Aggregate data for both datasets
    agg_main = aggregate_by_dimension(df_main, model)
    agg_compare = aggregate_by_dimension(df_compare, model)

    # Get common dimensions
    dimensions_list = sorted(set(agg_main["dimension"]) & set(agg_compare["dimension"]))
    dimensions = [int(d) for d in dimensions_list]

    print(f"\nTask type: {task_type}")
    print(f"Dimensions analyzed: {dimensions}")
    print(
        f"Unique tasks: {main_label}: {df_main['task_id'].nunique()}, {compare_label}: {df_compare['task_id'].nunique()}"
    )
    print(
        f"Total runs: {main_label}: {len(df_main)}, {compare_label}: {len(df_compare)}"
    )
    print(f"Model used for cost calculation: {model}")

    print(
        f"\n{'Dimension':<10} {'Metric':<15} {main_label:<20} {compare_label:<20} {'Difference':<15}"
    )
    print("-" * 85)

    for dim in dimensions:
        main_row = agg_main[agg_main["dimension"] == dim]
        compare_row = agg_compare[agg_compare["dimension"] == dim]

        if len(main_row) == 0 or len(compare_row) == 0:
            continue

        # Accuracy
        acc_main = float(main_row.iloc[0]["accuracy_rate"])
        acc_compare = float(compare_row.iloc[0]["accuracy_rate"])
        acc_diff = acc_main - acc_compare

        print(
            f"{dim:<10} {'Success Rate':<15} {acc_main:<19.1f}% {acc_compare:<19.1f}% {acc_diff:+.1f}%"
        )

        # Duration
        dur_main = float(main_row.iloc[0]["duration_min"])
        dur_compare = float(compare_row.iloc[0]["duration_min"])
        dur_diff = dur_main - dur_compare

        print(
            f"{'':<10} {'Duration':<15} {dur_main:<19.1f}m {dur_compare:<19.1f}m {dur_diff:+.1f}m"
        )

        # Cost
        cost_main = float(main_row.iloc[0]["cost"])
        cost_compare = float(compare_row.iloc[0]["cost"])
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
    overall_acc_main = agg_main["accuracy_rate"].mean()
    overall_acc_compare = agg_compare["accuracy_rate"].mean()
    overall_acc_diff = overall_acc_main - overall_acc_compare
    print(
        f"{'Avg Success Rate':<20} {overall_acc_main:<19.1f}% {overall_acc_compare:<19.1f}% {overall_acc_diff:+.1f}%"
    )

    # Overall duration
    overall_dur_main = agg_main["duration_min"].mean()
    overall_dur_compare = agg_compare["duration_min"].mean()
    overall_dur_diff = overall_dur_main - overall_dur_compare
    print(
        f"{'Avg Duration':<20} {overall_dur_main:<19.1f}m {overall_dur_compare:<19.1f}m {overall_dur_diff:+.1f}m"
    )

    # Overall cost
    overall_cost_main = agg_main["cost"].mean()
    overall_cost_compare = agg_compare["cost"].mean()
    overall_cost_diff = overall_cost_main - overall_cost_compare
    print(
        f"{'Avg Cost':<20} ${overall_cost_main:<18.3f} ${overall_cost_compare:<18.3f} ${overall_cost_diff:+.3f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze SentinelBench performance by task type"
    )
    parser.add_argument(
        "--sentinel-csv",
        type=str,
        required=True,
        help="Path to CSV file from run with sentinel tasks",
    )
    parser.add_argument(
        "--non-sentinel-csv",
        type=str,
        required=True,
        help="Path to CSV file from run without sentinel tasks",
    )
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        choices=list(MODEL_PRICING.keys()),
        help="Model name for cost calculation",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="plots/task_types",
        help="Directory to save plots (default: plots/task_types)",
    )
    parser.add_argument(
        "--output-prefix",
        type=str,
        default="task_type_comparison",
        help="Prefix for output files (default: task_type_comparison)",
    )

    args = parser.parse_args()

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Load data
    print("Loading data...")
    df_sentinel = pd.read_csv(args.sentinel_csv)
    df_non_sentinel = pd.read_csv(args.non_sentinel_csv)

    print(
        f"Loaded {len(df_sentinel)} tasks with sentinel, {len(df_non_sentinel)} tasks without sentinel"
    )

    # Process both task types
    for task_type in ["duration", "count"]:
        print(f"\n{'='*60}")
        print(f"Processing {task_type}-based tasks...")
        print(f"{'='*60}")

        # Filter data by task type
        sentinel_filtered = filter_tasks_by_type(df_sentinel, task_type)
        non_sentinel_filtered = filter_tasks_by_type(df_non_sentinel, task_type)

        if len(sentinel_filtered) == 0 or len(non_sentinel_filtered) == 0:
            print(f"No data found for {task_type}-based tasks. Skipping...")
            continue

        # Create plots
        base_path = os.path.join(args.output_dir, f"{args.output_prefix}.png")

        print(f"Creating {task_type}-based combined comparison plot...")
        create_combined_comparison_plot(
            non_sentinel_filtered,
            sentinel_filtered,
            task_type,
            args.model,
            "Without Sentinel",
            "With Sentinel",
            base_path,
        )

        # Print summary statistics
        print_summary_statistics(
            non_sentinel_filtered,
            sentinel_filtered,
            task_type,
            args.model,
            "Without Sentinel",
            "With Sentinel",
        )

    print(f"\nPlots saved to {args.output_dir}/")


if __name__ == "__main__":
    main()
