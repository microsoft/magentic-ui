#!/usr/bin/env python3
"""
Compare SentinelBench performance between runs with and without sentinel tasks.
Generates three comparison plots: accuracy, latency, and cost.
"""

import matplotlib.pyplot as plt
import matplotlib.style as style
from matplotlib.ticker import PercentFormatter
import pandas as pd
import numpy as np
import argparse
import os
from scipy import stats
from typing import Dict, List, Tuple, Optional


# Model def get_model_pricing():
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
return MODEL_PRICING


def setup_plot_style():
    """Set up consistent plot styling."""
    style.use("seaborn-v0_8-whitegrid")
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans"]
    plt.rcParams["font.size"] = 12
    plt.rcParams["axes.labelsize"] = 14
    plt.rcParams["axes.titlesize"] = 16
    plt.rcParams["xtick.labelsize"] = 11
    plt.rcParams["ytick.labelsize"] = 11
    plt.rcParams["legend.fontsize"] = 11


def calculate_cost(row: pd.Series, model: str) -> float:
    """Calculate cost for a task based on token usage and model pricing."""
    if model not in MODEL_PRICING:
        raise ValueError(f"Unknown model: {model}. Available models: {list(MODEL_PRICING.keys())}")
    
    pricing = MODEL_PRICING[model]
    prompt_tokens = row.get("total_prompt_tokens", 0)
    completion_tokens = row.get("total_completion_tokens", 0)
    
    # Calculate cost per 1K tokens
    input_cost = (prompt_tokens / 1000) * pricing["input"]
    output_cost = (completion_tokens / 1000) * pricing["output"]
    
    return input_cost + output_cost


def load_and_prepare_data(sentinel_csv: str, non_sentinel_csv: str, model: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load and prepare data from both CSV files."""
    df_sentinel = pd.read_csv(sentinel_csv)
    df_non_sentinel = pd.read_csv(non_sentinel_csv)
    
    # Add cost calculations
    df_sentinel["cost"] = df_sentinel.apply(lambda row: calculate_cost(row, model), axis=1)
    df_non_sentinel["cost"] = df_non_sentinel.apply(lambda row: calculate_cost(row, model), axis=1)
    
    # Add condition labels
    df_sentinel["condition"] = "With Sentinel"
    df_non_sentinel["condition"] = "Without Sentinel"
    
    return df_sentinel, df_non_sentinel


def statistical_test(data1: np.ndarray, data2: np.ndarray, test_type: str = "ttest") -> Tuple[float, float]:
    """Perform statistical test between two groups."""
    if test_type == "ttest":
        statistic, p_value = stats.ttest_ind(data1, data2, equal_var=False)
    elif test_type == "mannwhitney":
        statistic, p_value = stats.mannwhitneyu(data1, data2, alternative='two-sided')
    else:
        raise ValueError(f"Unknown test type: {test_type}")
    
    return statistic, p_value


def plot_accuracy_comparison(df_sentinel: pd.DataFrame, df_non_sentinel: pd.DataFrame, save_path: Optional[str] = None):
    """Create accuracy comparison plot by task."""
    setup_plot_style()
    
    # Get common tasks
    common_tasks = set(df_sentinel['task_id']) & set(df_non_sentinel['task_id'])
    common_tasks = sorted(list(common_tasks))
    
    if not common_tasks:
        raise ValueError("No common tasks found between the two datasets")
    
    # Calculate accuracy for each task
    sentinel_acc = []
    non_sentinel_acc = []
    task_labels = []
    
    for task in common_tasks:
        sent_score = df_sentinel[df_sentinel['task_id'] == task]['score'].iloc[0]
        non_sent_score = df_non_sentinel[df_non_sentinel['task_id'] == task]['score'].iloc[0]
        
        sentinel_acc.append(sent_score * 100)  # Convert to percentage
        non_sentinel_acc.append(non_sent_score * 100)
        task_labels.append(task.replace('-', '\n'))  # Break long task names
    
    # Create plot
    x = np.arange(len(common_tasks))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(max(12, len(common_tasks) * 0.8), 6))
    
    bars1 = ax.bar(x - width/2, non_sentinel_acc, width, label='Without Sentinel', 
                   color='#808080', alpha=0.8)
    bars2 = ax.bar(x + width/2, sentinel_acc, width, label='With Sentinel', 
                   color='#8B008B', alpha=0.8)
    
    ax.set_xlabel('Task', fontweight='bold')
    ax.set_ylabel('Accuracy (%)', fontweight='bold')
    ax.set_title('Task Accuracy: With vs Without Sentinel', fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(task_labels, rotation=45, ha='right')
    ax.legend()
    ax.set_ylim(0, 105)
    ax.yaxis.set_major_formatter(PercentFormatter())
    
    # Add grid
    ax.yaxis.grid(True, linestyle='--', alpha=0.7)
    ax.set_axisbelow(True)
    
    # Statistical test
    statistic, p_value = statistical_test(np.array(sentinel_acc), np.array(non_sentinel_acc))
    ax.text(0.02, 0.98, f'Paired t-test p-value: {p_value:.4f}', transform=ax.transAxes, 
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path.replace('.png', '_accuracy.png'), dpi=300, bbox_inches='tight')
        plt.savefig(save_path.replace('.png', '_accuracy.pdf'), dpi=300, bbox_inches='tight')
        print(f"Accuracy plot saved to {save_path.replace('.png', '_accuracy.png')}")
    
    return fig, ax


def plot_latency_comparison(df_sentinel: pd.DataFrame, df_non_sentinel: pd.DataFrame, save_path: Optional[str] = None):
    """Create latency comparison plot by task."""
    setup_plot_style()
    
    # Get common tasks
    common_tasks = set(df_sentinel['task_id']) & set(df_non_sentinel['task_id'])
    common_tasks = sorted(list(common_tasks))
    
    # Calculate latency for each task (convert to minutes)
    sentinel_latency = []
    non_sentinel_latency = []
    task_labels = []
    
    for task in common_tasks:
        sent_duration = df_sentinel[df_sentinel['task_id'] == task]['duration'].iloc[0] / 60
        non_sent_duration = df_non_sentinel[df_non_sentinel['task_id'] == task]['duration'].iloc[0] / 60
        
        sentinel_latency.append(sent_duration)
        non_sentinel_latency.append(non_sent_duration)
        task_labels.append(task.replace('-', '\n'))
    
    # Create plot
    x = np.arange(len(common_tasks))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(max(12, len(common_tasks) * 0.8), 6))
    
    bars1 = ax.bar(x - width/2, non_sentinel_latency, width, label='Without Sentinel', 
                   color='#808080', alpha=0.8)
    bars2 = ax.bar(x + width/2, sentinel_latency, width, label='With Sentinel', 
                   color='#8B008B', alpha=0.8)
    
    ax.set_xlabel('Task', fontweight='bold')
    ax.set_ylabel('Duration (minutes)', fontweight='bold')
    ax.set_title('Task Duration: With vs Without Sentinel', fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(task_labels, rotation=45, ha='right')
    ax.legend()
    
    # Add grid
    ax.yaxis.grid(True, linestyle='--', alpha=0.7)
    ax.set_axisbelow(True)
    
    # Statistical test
    statistic, p_value = statistical_test(np.array(sentinel_latency), np.array(non_sentinel_latency))
    ax.text(0.02, 0.98, f'Paired t-test p-value: {p_value:.4f}', transform=ax.transAxes, 
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path.replace('.png', '_latency.png'), dpi=300, bbox_inches='tight')
        plt.savefig(save_path.replace('.png', '_latency.pdf'), dpi=300, bbox_inches='tight')
        print(f"Latency plot saved to {save_path.replace('.png', '_latency.png')}")
    
    return fig, ax


def plot_cost_comparison(df_sentinel: pd.DataFrame, df_non_sentinel: pd.DataFrame, model: str, save_path: Optional[str] = None):
    """Create cost comparison plot by task."""
    setup_plot_style()
    
    # Get common tasks
    common_tasks = set(df_sentinel['task_id']) & set(df_non_sentinel['task_id'])
    common_tasks = sorted(list(common_tasks))
    
    # Calculate cost for each task
    sentinel_cost = []
    non_sentinel_cost = []
    task_labels = []
    
    for task in common_tasks:
        sent_cost = df_sentinel[df_sentinel['task_id'] == task]['cost'].iloc[0]
        non_sent_cost = df_non_sentinel[df_non_sentinel['task_id'] == task]['cost'].iloc[0]
        
        sentinel_cost.append(sent_cost)
        non_sentinel_cost.append(non_sent_cost)
        task_labels.append(task.replace('-', '\n'))
    
    # Create plot
    x = np.arange(len(common_tasks))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(max(12, len(common_tasks) * 0.8), 6))
    
    bars1 = ax.bar(x - width/2, non_sentinel_cost, width, label='Without Sentinel', 
                   color='#808080', alpha=0.8)
    bars2 = ax.bar(x + width/2, sentinel_cost, width, label='With Sentinel', 
                   color='#8B008B', alpha=0.8)
    
    ax.set_xlabel('Task', fontweight='bold')
    ax.set_ylabel('Cost (USD)', fontweight='bold')
    ax.set_title(f'Task Cost ({model}): With vs Without Sentinel', fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(task_labels, rotation=45, ha='right')
    ax.legend()
    
    # Add grid
    ax.yaxis.grid(True, linestyle='--', alpha=0.7)
    ax.set_axisbelow(True)
    
    # Statistical test
    statistic, p_value = statistical_test(np.array(sentinel_cost), np.array(non_sentinel_cost))
    ax.text(0.02, 0.98, f'Paired t-test p-value: {p_value:.4f}', transform=ax.transAxes, 
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path.replace('.png', '_cost.png'), dpi=300, bbox_inches='tight')
        plt.savefig(save_path.replace('.png', '_cost.pdf'), dpi=300, bbox_inches='tight')
        print(f"Cost plot saved to {save_path.replace('.png', '_cost.png')}")
    
    return fig, ax


def print_summary_statistics(df_sentinel: pd.DataFrame, df_non_sentinel: pd.DataFrame, model: str):
    """Print summary statistics comparing the two conditions."""
    print("\n" + "="*60)
    print("SUMMARY STATISTICS")
    print("="*60)
    
    # Overall accuracy
    sent_acc = df_sentinel['score'].mean() * 100
    non_sent_acc = df_non_sentinel['score'].mean() * 100
    print(f"Overall Accuracy:")
    print(f"  Without Sentinel: {non_sent_acc:.1f}%")
    print(f"  With Sentinel: {sent_acc:.1f}%")
    print(f"  Improvement: {sent_acc - non_sent_acc:+.1f} percentage points")
    
    # Overall latency
    sent_lat = df_sentinel['duration'].mean() / 60
    non_sent_lat = df_non_sentinel['duration'].mean() / 60
    print(f"\nAverage Duration:")
    print(f"  Without Sentinel: {non_sent_lat:.1f} minutes")
    print(f"  With Sentinel: {sent_lat:.1f} minutes")
    print(f"  Change: {sent_lat - non_sent_lat:+.1f} minutes")
    
    # Overall cost
    sent_cost = df_sentinel['cost'].mean()
    non_sent_cost = df_non_sentinel['cost'].mean()
    print(f"\nAverage Cost per Task ({model}):")
    print(f"  Without Sentinel: ${non_sent_cost:.4f}")
    print(f"  With Sentinel: ${sent_cost:.4f}")
    print(f"  Change: ${sent_cost - non_sent_cost:+.4f}")
    
    # Statistical significance tests
    print(f"\nStatistical Tests (p-values):")
    _, p_acc = statistical_test(df_sentinel['score'], df_non_sentinel['score'])
    _, p_lat = statistical_test(df_sentinel['duration'], df_non_sentinel['duration'])
    _, p_cost = statistical_test(df_sentinel['cost'], df_non_sentinel['cost'])
    
    print(f"  Accuracy difference: p = {p_acc:.4f}")
    print(f"  Duration difference: p = {p_lat:.4f}")
    print(f"  Cost difference: p = {p_cost:.4f}")


def main():
    parser = argparse.ArgumentParser(description="Compare SentinelBench performance with/without sentinel tasks")
    parser.add_argument("--sentinel-csv", type=str, required=True, 
                        help="Path to CSV file from run with sentinel tasks")
    parser.add_argument("--non-sentinel-csv", type=str, required=True, 
                        help="Path to CSV file from run without sentinel tasks")
    parser.add_argument("--model", type=str, required=True, choices=list(MODEL_PRICING.keys()),
                        help="Model name for cost calculation")
    parser.add_argument("--output-dir", type=str, default="plots", 
                        help="Directory to save plots (default: plots)")
    parser.add_argument("--output-prefix", type=str, default="sentinel_comparison",
                        help="Prefix for output files (default: sentinel_comparison)")
    
    args = parser.parse_args()
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Load and prepare data
    print("Loading data...")
    df_sentinel, df_non_sentinel = load_and_prepare_data(args.sentinel_csv, args.non_sentinel_csv, args.model)
    
    print(f"Loaded {len(df_sentinel)} tasks with sentinel, {len(df_non_sentinel)} tasks without sentinel")
    
    # Create plots
    base_path = os.path.join(args.output_dir, f"{args.output_prefix}.png")
    
    print("Creating accuracy comparison plot...")
    plot_accuracy_comparison(df_sentinel, df_non_sentinel, base_path)
    
    print("Creating latency comparison plot...")
    plot_latency_comparison(df_sentinel, df_non_sentinel, base_path)
    
    print("Creating cost comparison plot...")
    plot_cost_comparison(df_sentinel, df_non_sentinel, args.model, base_path)
    
    # Print summary statistics
    print_summary_statistics(df_sentinel, df_non_sentinel, args.model)
    
    print(f"\nPlots saved to {args.output_dir}/")


if __name__ == "__main__":
    main()