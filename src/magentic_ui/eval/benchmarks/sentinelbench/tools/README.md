# SentinelBench Analysis Tools

This directory contains specialized analysis and comparison tools for SentinelBench evaluation results.

## 📋 Prerequisites

1. **Run Evaluations First**: Before using these tools, you must have evaluation data from SentinelBench runs.
2. **Dependencies**: Ensure you have the required packages installed (`pandas`, `matplotlib`, `typer`, etc.)

## 📁 Available Tools

### 🛠️ Analysis Tools
- **[`single_task_performance.py`](#single_task_performance)** - Core analysis script for individual tasks with dimension scaling
- **[`full_benchmark_comparison.py`](#full_benchmark_comparison)** - Run comprehensive comparisons across all tasks 
- **[`task_type_comparison.py`](#task_type_comparison)** - Analyze task performance by type (duration vs count-based)
- **[`missing_runs_checker.py`](#missing_runs_checker)** - Check for missing evaluation runs

---

## 🏃‍♂️ Quick Start Guide

### Step 1: Run SentinelBench Evaluations


# Set your config in config.yaml
# Start hosting the SentinelBench 

First, run your evaluations using the main evaluation runner:

For consistency, we use dir 0 for runs using non sentinel steps and dir 1 for sentinel steps

Based on your system, you may also increase the parallel number to run tasks simultaneously, but you may hit rate limits from LLM providers, in which case you can either have multiple keys or use a lower # of parallel tasks

```bash
# Run WITHOUT sentinel steps
python experiments/eval/run.py \
  --current-dir . \
  --dataset SentinelBench \
  --split test \
  --run-id 0 \
  --simulated-user-type none \
  --parallel 1 \
  --config experiments/endpoint_configs/config.yaml \
  --mode run \
  --use-local-browser \
  --web-surfer-only 

# Run WITH sentinel steps
python experiments/eval/run.py \
  --current-dir . \
  --dataset SentinelBench \
  --split test \
  --run-id 1 \
  --simulated-user-type none \
  --parallel 1 \
  --config experiments/endpoint_configs/config.yaml \
  --mode run \ 
  --use-local-browser \
  --web-surfer-only \
  --enable-sentinel
```

### Step 2: Evaluate Results

(note that if the --run executed fully, it automatically runs the --eval, otherwise you have to run the same command above but with the --eval flag, as seen below)

Convert raw execution results to evaluation scores:

Note that if you used --web-surfer-only for running the tasks, you must also use it for evaluating the tasks below as it stores the runs in a directory with a different name.

```bash
# Evaluate results without SentinelSteps (dir. 0)
python experiments/eval/run.py \
  --current-dir . \
  --dataset SentinelBench \
  --split test \
  --run-id 0 \
  --mode eval \
  --web-surfer-only 

# Evaluate results with SentinelSteps (dir. 1)
python experiments/eval/run.py \
  --current-dir . \
  --dataset SentinelBench \
  --split test \
  --run-id 1 \
  --mode eval \
  --web-surfer-only \
  --enable-sentinel
```

### Step 3: Generate Comprehensive Comparison

```bash
# Recommended: Evaluation with all data
python src/magentic_ui/eval/benchmarks/sentinelbench/tools/full_benchmark_comparison.py \
  --model gpt-5-mini \ 
  --union-fill \
  --output-dir plots/comprehensive_comparison
```

---

## 🔧 Tool Details

### single_task_performance

**Purpose**: Core analysis engine for individual SentinelBench tasks. Analyzes how performance scales across task dimensions and supports detailed comparisons.

**Key Features**:
- 📊 Single task dimension scaling analysis
- 🔄 Comparison between two runs (with/without sentinel)
- 📈 Beautiful publication-ready plots
- 💾 CSV data export with processed metrics
- ⚖️ Intersection/union dimension alignment

**Usage**:
```bash
python src/magentic_ui/eval/benchmarks/sentinelbench/tools/single_task_performance.py [OPTIONS]
```

**Core Options**:
- `--run-dir DIR` - Path to run directory **[REQUIRED]**
- `--task-name TASK` - Task name (e.g., `reactor-easy`) **[REQUIRED]**
- `--model MODEL` - Model for cost calculation **[REQUIRED]**
- `--output-dir DIR` - Output directory (default: `plots`)

**Analysis Options**:
- `--compare-with DIR` - Second run directory for comparison
- `--main-label LABEL` - Label for main run (default: "Run 1")
- `--compare-label LABEL` - Label for comparison run (default: "Run 2")

**Output Options**:
- `--combined` - Create combined plot with all metrics ⭐ **Recommended**
- `--save-csv` - Export processed data to CSV
- `--sentinel` - Add sentinel suffix to plots (single run mode)

**Dimension Alignment** (comparison mode):
- `--intersection-only` - Only shared dimensions
- `--union-fill` - All dimensions, fill missing with artificial entries

**Examples**:
```bash
# Single task analysis with comparison
python src/magentic_ui/eval/benchmarks/sentinelbench/tools/single_task_performance.py \
  --run-dir runs/MagenticUI_web_surfer_only/SentinelBench/test/0 \
  --compare-with runs/MagenticUI_web_surfer_only/SentinelBench/test/1 \
  --task-name reactor-easy \
  --model gpt-5-mini \
  --combined \
  --union-fill

# Single run analysis
python src/magentic_ui/eval/benchmarks/sentinelbench/tools/single_task_performance.py \
  --run-dir runs/MagenticUI_web_surfer_only/SentinelBench/test/1 \
  --task-name button-presser-medium \
  --model gpt-5-mini \
  --sentinel \
  --combined
```

### full_benchmark_comparison

**Purpose**: Run comprehensive performance comparisons between "With Sentinel" vs "Without Sentinel" across all SentinelBench tasks.

**Key Features**:
- 🎯 Automated task discovery and filtering
- 📊 Individual task analysis and aggregation  
- 🎨 Beautiful comparison plots and statistics
- ⚖️ Multiple data alignment strategies

**Usage**:
```bash
python src/magentic_ui/eval/benchmarks/sentinelbench/tools/full_benchmark_comparison.py [OPTIONS]
```

**Core Options**:
- `--model MODEL` - Model for cost calculation (e.g., `gpt-5-mini`) **[REQUIRED]**
- `--output-dir DIR` - Output directory (default: `plots/FINAL`)

**Data Selection**:  
- `--include-failed-runs` - Include failed runs for honest evaluation ⭐ **Recommended**
- `--include-single-dir` - Include tasks only in one directory  
- `--check-messages` - Use messages.json for validation instead of exact answer match

**Dimension Alignment**:
- `--intersection-only` - Only dimensions in BOTH directories (AND operation)
- `--union-fill` - ALL dimensions, fill missing with artificial entries (UNION) ⭐ **Recommended**

**Processing**:
- `--skip-individual` - Skip individual task analysis, only do combined

**Examples**:
```bash
# 🏆 Recommended: Complete honest evaluation
python src/magentic_ui/eval/benchmarks/sentinelbench/tools/full_benchmark_comparison.py \
  --model gpt-5-mini \
  --include-failed-runs \
  --union-fill

# Conservative: Only shared successful runs
python src/magentic_ui/eval/benchmarks/sentinelbench/tools/full_benchmark_comparison.py \
  --model gpt-5-mini \
  --intersection-only

# Quick overview: Skip individual plots
python src/magentic_ui/eval/benchmarks/sentinelbench/tools/full_benchmark_comparison.py \
  --model gpt-5-mini \
  --skip-individual
```

### task_type_comparison

**Purpose**: Analyze and compare task performance by task type (duration-based vs count-based tasks).

**Usage**:
```bash
python src/magentic_ui/eval/benchmarks/sentinelbench/tools/task_type_comparison.py [OPTIONS]
```

**Key Options**:
- `--csv-without FILE` - CSV file for "without sentinel" results
- `--csv-with FILE` - CSV file for "with sentinel" results  
- `--model MODEL` - Model for cost calculations
- `--output-dir DIR` - Output directory for plots

**Example**:
```bash
python src/magentic_ui/eval/benchmarks/sentinelbench/tools/task_type_comparison.py \
  --csv-without plots/FINAL/all_tasks_without_sentinel.csv \
  --csv-with plots/FINAL/all_tasks_with_sentinel.csv \
  --model gpt-5-mini \
  --output-dir plots/task_type_analysis
```

### missing_runs_checker

**Purpose**: Check for missing evaluation runs and identify gaps in your dataset.

**Usage**:
```bash
python src/magentic_ui/eval/benchmarks/sentinelbench/tools/missing_runs_checker.py [OPTIONS]
```

**Key Options**:
- `--check-messages` - Use messages.json validation
- `--include-failed-runs` - Include failed runs in analysis

**Example**:
```bash
python src/magentic_ui/eval/benchmarks/sentinelbench/tools/missing_runs_checker.py \
  --include-failed-runs
```

---

## 📊 Understanding the Parameters

### 🎯 Key Flags Explained

#### `--include-failed-runs` ⭐ **Highly Recommended**
- **What**: Includes tasks that failed, timed out, or crashed  
- **Why**: Provides honest evaluation showing real-world performance
- **Without**: Only "cherry-picked" successful runs (biased results)
- **With**: Complete picture including failures and edge cases

#### `--union-fill` ⭐ **Recommended for Complete Analysis**  
- **What**: Includes ALL task+dimension combinations from both runs
- **Why**: Ensures equal comparison basis  
- **Result**: Missing combinations filled with artificial entries (score=0.0, representing failure)
- **Alternative**: `--intersection-only` (only shared dimensions)

#### `--include-single-dir`
- **What**: Includes tasks that only have data in one directory
- **Why**: More comprehensive dataset  
- **Use case**: When some tasks only succeeded in one condition

### 📈 Output Files

The tools generate several types of output:

**Individual Task Analysis**:
- `{task}-comparison_combined_comparison.png` - Combined metrics plot
- `{task}-comparison_with_sentinel_analysis.csv` - Raw data with sentinel
- `{task}-comparison_without_sentinel_analysis.csv` - Raw data without sentinel

**Aggregate Analysis**:
- `all_tasks_comparison_accuracy.png` - Overall accuracy comparison
- `all_tasks_comparison_latency.png` - Overall latency comparison  
- `all_tasks_comparison_cost.png` - Overall cost comparison
- `all_tasks_with_sentinel.csv` - Combined dataset with sentinel
- `all_tasks_without_sentinel.csv` - Combined dataset without sentinel

---

## 🚦 Common Workflows

### 🔬 Research Workflow
1. Run evaluations with/without sentinel
2. Use `full_benchmark_comparison.py` with `--union-fill --include-failed-runs` 
3. Analyze results with `task_type_comparison.py`
4. Check data completeness with `missing_runs_checker.py`

### ⚡ Quick Check Workflow  
1. Run evaluations
2. Use `full_benchmark_comparison.py` with `--skip-individual` for quick overview
3. Drill down with individual task analysis if needed

### 🔍 Debug Workflow
1. Use `missing_runs_checker.py` to identify gaps
2. Re-run missing evaluations  
3. Use `full_benchmark_comparison.py` with appropriate flags

---

## 💡 Tips & Best Practices

1. **Always use `--include-failed-runs`** for honest evaluation
2. **Use `--union-fill`** for comprehensive comparisons  
3. **Check data completeness** with `missing_runs_checker.py` before analysis
4. **Start with `--skip-individual`** for quick overviews
5. **Use specific models** (e.g., `gpt-5-mini`) for accurate cost calculations

---

## 🐛 Troubleshooting

### "No tasks found"
- Check that evaluation data exists in `runs/` directory
- Use `--include-failed-runs` or `--include-single-dir` flags
- Verify run IDs (0 and 1) match your evaluation setup

### "Missing dimensions"  
- Use `--union-fill` to include all dimensions with artificial entries
- Check that both runs cover the same task variants

### Path Issues
- Run tools from project root directory
- Verify `runs/MagenticUI_web_surfer_only/SentinelBench/test/` exists

---

## 📞 Support

For issues with these tools, check:
1. Evaluation data exists and is complete
2. All dependencies are installed  
3. Running from correct directory (project root)
4. Using appropriate flags for your use case