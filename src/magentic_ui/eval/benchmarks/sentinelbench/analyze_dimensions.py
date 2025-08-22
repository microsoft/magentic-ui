#!/usr/bin/env python3
"""
Analyze SentinelBench performance across task dimensions.
Creates plots showing accuracy, latency, and cost scaling for specific tasks.

Usage:
    python analyze_dimensions.py --run-dir runs/MagenticUI/SentinelBench/test/4000 \
                                 --task-name animal-mover-easy \
                                 --model gpt-4o \
                                 --output-dir plots
"""

import matplotlib.pyplot as plt
import matplotlib.style as style
from matplotlib.ticker import PercentFormatter, FuncFormatter
import pandas as pd
import numpy as np
import argparse
import os
import json
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Model pricing (from compare_sentinel_performance.py)
MODEL_PRICING = {
    # OpenAI GPT
    "gpt-4o": {"input": 0.005, "output": 0.02},  # Standard
    "gpt-4o-batch": {"input": 0.0025, "output": 0.01},  # Batch/Azure
    "gpt-4o-2024-08-06": {"input": 0.005, "output": 0.02},
    "gpt-4o-2024-11-20": {"input": 0.005, "output": 0.02},
    "gpt-4o-mini": {"input": 0.0006, "output": 0.0024},  # Standard (Batch = 0.0003/0.0012)
    "gpt-4o-mini-2024-07-18": {"input": 0.0006, "output": 0.0024},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "gpt-5-mini": {"input": 0.00025, "output": 0.002},  # GPT-5 mini: $0.25/$2.00 per 1M tokens

    # Anthropic Claude
    "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
    "claude-3-5-sonnet-20240620": {"input": 0.003, "output": 0.015},
    "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
    "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},

    # Google Gemini
    "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},  # ≤128k ctx
    "gemini-1.5-pro-extended": {"input": 0.0025, "output": 0.01},  # >128k ctx
    "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},  # ≤128k ctx
    "gemini-1.5-flash-extended": {"input": 0.00015, "output": 0.0006},  # >128k ctx
}

def setup_plot_style():
    """Set up beautiful, paper-ready plot styling with light purple cartoonish theme."""
    # Use a clean, modern style as base
    plt.style.use('default')
    
    # Font settings for academic papers
    plt.rcParams["font.family"] = "serif"
    plt.rcParams["font.serif"] = ["Times New Roman", "Times", "serif"]
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
    plt.rcParams["axes.prop_cycle"] = plt.cycler('color', [
        '#9D7FE0',  # Light purple
        '#B19FE8',  # Lighter purple
        '#C5BFF0',  # Very light purple
        '#E8E3F8',  # Pale purple
        '#F5F3FC',  # Almost white purple
    ])
    
    # Clean, modern appearance
    plt.rcParams["axes.spines.top"] = False
    plt.rcParams["axes.spines.right"] = False
    plt.rcParams["axes.spines.left"] = True
    plt.rcParams["axes.spines.bottom"] = True
    plt.rcParams["axes.linewidth"] = 1.2
    plt.rcParams["axes.edgecolor"] = '#666666'
    
    # Grid styling
    plt.rcParams["axes.grid"] = True
    plt.rcParams["grid.alpha"] = 0.3
    plt.rcParams["grid.linewidth"] = 0.8
    plt.rcParams["grid.color"] = '#CCCCCC'
    
    # Background colors
    plt.rcParams["figure.facecolor"] = 'white'
    plt.rcParams["axes.facecolor"] = '#FEFEFE'

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
    task_dirs = [d for d in run_path.iterdir() if d.is_dir() and d.name.startswith(task_name)]
    
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
                logger.warning(f"No times.json found for {task_name} dimension {dimension}")
                continue
            
            # Load answer data
            answer_files = list(dim_dir.glob(f"{task_name}_{dimension}_answer.json"))
            if answer_files:
                with open(answer_files[0]) as f:
                    answer_data = json.load(f)
                    task_data["answer"] = answer_data.get("answer", "")
            else:
                logger.warning(f"No answer file found for {task_name} dimension {dimension}")
                task_data["answer"] = ""
            
            # Load token usage data
            tokens_file = dim_dir / "model_tokens_usage.json"
            if tokens_file.exists():
                with open(tokens_file) as f:
                    token_data = json.load(f)
                    total_data = token_data.get("total_without_user_proxy", {})
                    task_data["prompt_tokens"] = total_data.get("prompt_tokens", 0)
                    task_data["completion_tokens"] = total_data.get("completion_tokens", 0)
                    task_data["total_tokens"] = task_data["prompt_tokens"] + task_data["completion_tokens"]
            else:
                logger.warning(f"No token usage file found for {task_name} dimension {dimension}")
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
                logger.warning(f"No score.json found for {task_name} dimension {dimension}")
                task_data["score"] = None
            
            data.append(task_data)
    
    if not data:
        raise ValueError(f"No valid data found for task '{task_name}'")
    
    df = pd.DataFrame(data)
    df = df.sort_values("dimension")  # Sort by dimension
    
    logger.info(f"Loaded data for {len(df)} dimension variants of task '{task_name}'")
    logger.info(f"Dimensions found: {sorted(df['dimension'].unique())}")
    
    return df

def analyze_accuracy(df: pd.DataFrame) -> pd.DataFrame:
    """
    Analyze accuracy based on evaluation scores from score.json files.
    Falls back to completion status if scores are not available.
    """
    # Check if we have evaluation scores
    if "score" in df.columns and df["score"].notna().sum() > 0:
        # Use real evaluation scores
        logger.info("Using evaluation scores for accuracy analysis")
        df["accuracy"] = (df["score"] > 0).astype(int)
    else:
        # Fallback to completion-based proxy
        logger.warning("No evaluation scores found, using completion status as accuracy proxy")
        df["accuracy"] = ((df["completed"] == True) & (~df["has_timeout"]) & (~df["interrupted"])).astype(int)
    
    # Group by dimension and calculate accuracy rate
    accuracy_by_dim = df.groupby("dimension").agg({
        "accuracy": ["mean", "count"],
        "has_timeout": "sum",
        "interrupted": "sum"
    }).round(4)
    
    # Flatten column names
    accuracy_by_dim.columns = ["accuracy_rate", "total_tasks", "timeout_count", "interrupted_count"]
    accuracy_by_dim = accuracy_by_dim.reset_index()
    
    return accuracy_by_dim

def plot_accuracy_vs_dimension(df: pd.DataFrame, task_name: str, save_path: Optional[str] = None):
    """Create accuracy vs dimension plot."""
    setup_plot_style()
    
    accuracy_data = analyze_accuracy(df)
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    dimensions = accuracy_data["dimension"]
    accuracy_rates = accuracy_data["accuracy_rate"] * 100  # Convert to percentage
    
    # Create evenly spaced x positions (treat dimensions as categorical)
    x_positions = range(len(dimensions))
    
    # Create beautiful bar plot with gradient effect
    bars = ax.bar(x_positions, accuracy_rates, 
                  color='#B19FE8', alpha=0.85, 
                  edgecolor='#7B68C7', linewidth=1.5,
                  capstyle='round')
    
    # Add elegant value labels on bars
    for i, (bar, acc) in enumerate(zip(bars, accuracy_rates)):
        height = bar.get_height()
        ax.text(i, height + 1,
                f'{acc:.1f}%', ha='center', va='bottom', 
                fontweight='bold', fontsize=12, color='#5A4B7B')
    
    ax.set_xlabel('Task Dimension', fontweight='bold')
    ax.set_ylabel('Success Rate (%)', fontweight='bold')
    ax.set_title(f'Success Rate vs Dimension: {task_name.replace("-", " ").title()}', fontweight='bold')
    ax.set_ylim(0, 105)
    ax.yaxis.set_major_formatter(PercentFormatter())
    
    # Set x-axis with evenly spaced categorical labels
    ax.set_xticks(x_positions)
    ax.set_xticklabels(dimensions)
    
    # Beautiful grid styling (already set in rcParams)
    ax.set_axisbelow(True)
    
    plt.tight_layout()
    
    if save_path:
        accuracy_path = save_path.replace('.png', '_accuracy.png')
        plt.savefig(accuracy_path, dpi=300, bbox_inches='tight')
        plt.savefig(accuracy_path.replace('.png', '.pdf'), dpi=300, bbox_inches='tight')
        logger.info(f"Accuracy plot saved to {accuracy_path}")
    
    return fig, ax

def plot_latency_vs_dimension(df: pd.DataFrame, task_name: str, save_path: Optional[str] = None):
    """Create latency vs dimension plot."""
    setup_plot_style()
    
    # Group by dimension and calculate mean latency (in minutes)
    latency_data = df.groupby("dimension").agg({
        "duration": ["mean", "std", "count"]
    }).round(2)
    
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
    bars = ax.bar(x_positions, mean_latencies, 
                  yerr=std_latencies, capsize=6,
                  color='#9D7FE0', alpha=0.85, 
                  edgecolor='#6A5ACD', linewidth=1.5,
                  capstyle='round', error_kw={'color': '#5A4B7B', 'linewidth': 2})
    
    # Add elegant value labels on bars
    for i, (bar, lat) in enumerate(zip(bars, mean_latencies)):
        height = bar.get_height()
        ax.text(i, height + max(std_latencies) * 0.1,
                f'{lat:.1f}m', ha='center', va='bottom', 
                fontweight='bold', fontsize=12, color='#5A4B7B')
    
    ax.set_xlabel('Task Dimension', fontweight='bold')
    ax.set_ylabel('Average Duration (minutes)', fontweight='bold')
    ax.set_title(f'Task Duration vs Dimension: {task_name.replace("-", " ").title()}', fontweight='bold')
    
    # Set x-axis with evenly spaced categorical labels
    ax.set_xticks(x_positions)
    ax.set_xticklabels(dimensions)
    
    # Beautiful grid styling (already set in rcParams)
    ax.set_axisbelow(True)
    
    plt.tight_layout()
    
    if save_path:
        latency_path = save_path.replace('.png', '_latency.png')
        plt.savefig(latency_path, dpi=300, bbox_inches='tight')
        plt.savefig(latency_path.replace('.png', '.pdf'), dpi=300, bbox_inches='tight')
        logger.info(f"Latency plot saved to {latency_path}")
    
    return fig, ax

def plot_cost_vs_dimension(df: pd.DataFrame, task_name: str, model: str, save_path: Optional[str] = None):
    """Create cost vs dimension plot."""
    setup_plot_style()
    
    # Calculate costs
    df["cost"] = df.apply(lambda row: calculate_cost(row["prompt_tokens"], row["completion_tokens"], model), axis=1)
    
    # Group by dimension and calculate mean cost
    cost_data = df.groupby("dimension").agg({
        "cost": ["mean", "std", "count"]
    }).round(4)
    
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
    bars = ax.bar(x_positions, mean_costs, 
                  yerr=std_costs, capsize=6,
                  color='#C5BFF0', alpha=0.85, 
                  edgecolor='#8A7CA8', linewidth=1.5,
                  capstyle='round', error_kw={'color': '#5A4B7B', 'linewidth': 2})
    
    # Add elegant value labels on bars
    for i, (bar, cost) in enumerate(zip(bars, mean_costs)):
        height = bar.get_height()
        ax.text(i, height + max(std_costs) * 0.1,
                f'${cost:.3f}', ha='center', va='bottom', 
                fontweight='bold', fontsize=12, color='#5A4B7B')
    
    ax.set_xlabel('Task Dimension', fontweight='bold')
    ax.set_ylabel('Average Cost (USD)', fontweight='bold')
    ax.set_title(f'Task Cost vs Dimension: {task_name.replace("-", " ").title()} ({model})', fontweight='bold')
    
    # Set x-axis with evenly spaced categorical labels
    ax.set_xticks(x_positions)
    ax.set_xticklabels(dimensions)
    
    # Format y-axis to show currency
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f'${x:.3f}'))
    
    # Beautiful grid styling (already set in rcParams)
    ax.set_axisbelow(True)
    
    plt.tight_layout()
    
    if save_path:
        cost_path = save_path.replace('.png', '_cost.png')
        plt.savefig(cost_path, dpi=300, bbox_inches='tight')
        plt.savefig(cost_path.replace('.png', '.pdf'), dpi=300, bbox_inches='tight')
        logger.info(f"Cost plot saved to {cost_path}")
    
    return fig, ax

def create_combined_plot(df: pd.DataFrame, task_name: str, model: str, save_path: Optional[str] = None):
    """Create a combined plot with all three metrics."""
    setup_plot_style()
    
    # Calculate all metrics
    accuracy_data = analyze_accuracy(df)
    df["cost"] = df.apply(lambda row: calculate_cost(row["prompt_tokens"], row["completion_tokens"], model), axis=1)
    
    latency_data = df.groupby("dimension").agg({
        "duration": "mean"
    }).reset_index()
    latency_data["duration_min"] = latency_data["duration"] / 60
    
    cost_data = df.groupby("dimension").agg({
        "cost": "mean"
    }).reset_index()
    
    # Create beautiful subplots with nice spacing
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(20, 6))
    fig.patch.set_facecolor('white')
    
    # Plot 1: Accuracy
    dimensions = accuracy_data["dimension"]
    accuracy_rates = accuracy_data["accuracy_rate"] * 100
    
    # Create evenly spaced x positions for all plots
    x_positions = range(len(dimensions))
    
    bars1 = ax1.bar(x_positions, accuracy_rates, 
                     color='#B19FE8', alpha=0.85, 
                     edgecolor='#7B68C7', linewidth=1.5, capstyle='round')
    for i, (bar, acc) in enumerate(zip(bars1, accuracy_rates)):
        height = bar.get_height()
        ax1.text(i, height + 1,
                f'{acc:.1f}%', ha='center', va='bottom', 
                fontsize=11, fontweight='bold', color='#5A4B7B')
    
    ax1.set_xlabel('Task Dimension', fontweight='bold')
    ax1.set_ylabel('Success Rate (%)', fontweight='bold')
    ax1.set_title('Success Rate', fontweight='bold')
    ax1.set_ylim(0, 105)
    ax1.yaxis.set_major_formatter(PercentFormatter())
    ax1.set_xticks(x_positions)
    ax1.set_xticklabels(dimensions)
    ax1.set_axisbelow(True)
    
    # Plot 2: Latency
    latencies = latency_data["duration_min"]
    bars2 = ax2.bar(x_positions, latencies, 
                    color='#9D7FE0', alpha=0.85, 
                    edgecolor='#6A5ACD', linewidth=1.5, capstyle='round')
    for i, (bar, lat) in enumerate(zip(bars2, latencies)):
        height = bar.get_height()
        ax2.text(i, height * 1.02,
                f'{lat:.1f}m', ha='center', va='bottom', 
                fontsize=11, fontweight='bold', color='#5A4B7B')
    
    ax2.set_xlabel('Task Dimension', fontweight='bold')
    ax2.set_ylabel('Duration (minutes)', fontweight='bold')
    ax2.set_title('Task Duration', fontweight='bold')
    ax2.set_xticks(x_positions)
    ax2.set_xticklabels(dimensions)
    ax2.set_axisbelow(True)
    
    # Plot 3: Cost
    costs = cost_data["cost"]
    bars3 = ax3.bar(x_positions, costs, 
                    color='#C5BFF0', alpha=0.85, 
                    edgecolor='#8A7CA8', linewidth=1.5, capstyle='round')
    for i, (bar, cost) in enumerate(zip(bars3, costs)):
        height = bar.get_height()
        ax3.text(i, height * 1.02,
                f'${cost:.3f}', ha='center', va='bottom', 
                fontsize=11, fontweight='bold', color='#5A4B7B')
    
    ax3.set_xlabel('Task Dimension', fontweight='bold')
    ax3.set_ylabel('Cost (USD)', fontweight='bold')
    ax3.set_title(f'Cost ({model})', fontweight='bold')
    ax3.set_xticks(x_positions)
    ax3.set_xticklabels(dimensions)
    ax3.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f'${x:.3f}'))
    ax3.set_axisbelow(True)
    
    # Add elegant overall title
    fig.suptitle(f'Performance Analysis: {task_name.replace("-", " ").title()}', 
                 fontsize=22, fontweight='bold', y=1.05, color='#5A4B7B')
    
    plt.tight_layout()
    
    if save_path:
        combined_path = save_path.replace('.png', '_combined.png')
        plt.savefig(combined_path, dpi=300, bbox_inches='tight')
        plt.savefig(combined_path.replace('.png', '.pdf'), dpi=300, bbox_inches='tight')
        logger.info(f"Combined plot saved to {combined_path}")
    
    return fig, (ax1, ax2, ax3)

def print_summary_statistics(df: pd.DataFrame, task_name: str, model: str):
    """Print comprehensive summary statistics."""
    print("\n" + "="*80)
    print(f"SUMMARY STATISTICS: {task_name.replace('-', ' ').title()}")
    print("="*80)
    
    # Calculate metrics
    accuracy_data = analyze_accuracy(df)
    df["cost"] = df.apply(lambda row: calculate_cost(row["prompt_tokens"], row["completion_tokens"], model), axis=1)
    
    print(f"\nDimensions analyzed: {sorted(df['dimension'].unique())}")
    print(f"Total task runs: {len(df)}")
    print(f"Model used for cost calculation: {model}")
    
    print(f"\n{'Dimension':<10} {'Success Rate':<12} {'Avg Duration':<15} {'Avg Cost':<10} {'Timeouts':<10}")
    print("-" * 65)
    
    for dim in sorted(df['dimension'].unique()):
        dim_data = df[df['dimension'] == dim]
        acc_row = accuracy_data[accuracy_data['dimension'] == dim].iloc[0]
        
        success_rate = acc_row['accuracy_rate'] * 100
        avg_duration = dim_data['duration'].mean() / 60  # Convert to minutes
        avg_cost = dim_data['cost'].mean()
        timeout_count = acc_row['timeout_count']
        
        print(f"{dim:<10} {success_rate:<11.1f}% {avg_duration:<14.1f}m ${avg_cost:<9.3f} {timeout_count:<10}")
    
    print(f"\nOverall Statistics:")
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
        print(f"  Score distribution: {perfect_scores} perfect (1.0), {partial_scores} partial (0-1), {zero_scores} failed (0.0)")

def main():
    parser = argparse.ArgumentParser(description="Analyze SentinelBench performance across task dimensions")
    parser.add_argument("--run-dir", type=str, required=True,
                        help="Path to run directory (e.g., runs/MagenticUI/SentinelBench/test/4000)")
    parser.add_argument("--task-name", type=str, required=True,
                        help="Name of the task to analyze (e.g., animal-mover-easy)")
    parser.add_argument("--model", type=str, required=True, choices=list(MODEL_PRICING.keys()),
                        help="Model name for cost calculation")
    parser.add_argument("--output-dir", type=str, default="plots",
                        help="Directory to save plots (default: plots)")
    parser.add_argument("--output-prefix", type=str, default=None,
                        help="Prefix for output files (default: task-name)")
    parser.add_argument("--combined", action="store_true",
                        help="Create combined plot with all metrics")
    parser.add_argument("--save-csv", action="store_true",
                        help="Save processed data to CSV file")
    
    args = parser.parse_args()
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Set default output prefix
    if args.output_prefix is None:
        args.output_prefix = args.task_name.replace("/", "_").replace(" ", "_")
    
    try:
        # Load data
        logger.info(f"Loading data for task '{args.task_name}' from {args.run_dir}")
        df = load_task_data(args.run_dir, args.task_name)
        
        if len(df) == 0:
            logger.error("No data found. Exiting.")
            return
        
        # Save to CSV if requested
        if args.save_csv:
            csv_path = os.path.join(args.output_dir, f"{args.output_prefix}_analysis.csv")
            df.to_csv(csv_path, index=False)
            logger.info(f"Data saved to {csv_path}")
        
        # Create base path for plots
        base_path = os.path.join(args.output_dir, f"{args.output_prefix}.png")
        
        if args.combined:
            # Create combined plot
            logger.info("Creating combined analysis plot...")
            create_combined_plot(df, args.task_name, args.model, base_path)
        else:
            # Create individual plots
            logger.info("Creating accuracy plot...")
            plot_accuracy_vs_dimension(df, args.task_name, base_path)
            
            logger.info("Creating latency plot...")
            plot_latency_vs_dimension(df, args.task_name, base_path)
            
            logger.info("Creating cost plot...")
            plot_cost_vs_dimension(df, args.task_name, args.model, base_path)
        
        # Print summary statistics
        print_summary_statistics(df, args.task_name, args.model)
        
        logger.info(f"Analysis complete! Plots saved to {args.output_dir}/")
        
    except Exception as e:
        logger.error(f"Error during analysis: {e}")
        raise

if __name__ == "__main__":
    main()