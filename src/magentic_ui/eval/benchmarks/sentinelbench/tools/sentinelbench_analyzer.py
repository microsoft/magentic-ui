#!/usr/bin/env python3
"""
🚀 SentinelBench Unified Analyzer

Consolidated tool for all SentinelBench analysis tasks including:
- Single task analysis across dimensions
- Full directory analysis (all tasks)
- Comparison analysis (with vs without sentinel)
- Missing runs detection
- Task type analysis (duration vs count)

Usage Examples:
    # Quick missing runs check
    python sentinelbench_analyzer.py --quick-check --model gpt-5-mini

    # Analyze single task
    python sentinelbench_analyzer.py --single-task-analysis --task-name button-presser --model gpt-5-mini

    # Full analysis of one directory
    python sentinelbench_analyzer.py --single-comprehensive --model gpt-5-mini --main-dir 0

    # Complete comparison analysis
    python sentinelbench_analyzer.py --full-comparison --model gpt-5-mini

    # Everything
    python sentinelbench_analyzer.py --all-analysis --model gpt-5-mini
"""

import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter, FuncFormatter
import pandas as pd
import numpy as np
import typer
from typing_extensions import Annotated
import os
import json
from typing import Optional, List, Dict, Tuple, Any
from pathlib import Path
import logging
import sys
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Import from centralized task variants
try:
    from ..task_variants import (
        MODEL_PRICING,
        SENTINELBENCH_TASK_VARIANTS,
        DURATION_TASK_PATTERNS,
        COUNT_TASK_PATTERNS,
    )
except ImportError:
    # Fallback for direct execution
    sys.path.append(str(Path(__file__).parent.parent))
    from task_variants import (
        MODEL_PRICING,
        SENTINELBENCH_TASK_VARIANTS,
        DURATION_TASK_PATTERNS,
        COUNT_TASK_PATTERNS,
    )

# Configure typer app
app = typer.Typer(
    help="🚀 SentinelBench Unified Analyzer - All-in-one analysis tool",
    rich_markup_mode="rich",
    add_completion=False,
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SentinelBenchAnalyzer:
    """Main analyzer class containing all analysis functionality."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.setup_paths()
        self.setup_logging()
        
    def setup_paths(self):
        """Set up and validate paths."""
        # Resolve base_path from project root if relative
        base_path = self.config['base_path']
        if not Path(base_path).is_absolute():
            current_dir = Path.cwd()
            project_root = None
            
            for parent in [current_dir] + list(current_dir.parents):
                if (parent / "data" / "SentinelBench").exists():
                    project_root = parent
                    break
            
            if project_root:
                self.config['base_path'] = str(project_root / base_path)
            else:
                self.config['base_path'] = str(Path(base_path).resolve())
        
        # Create output directory
        os.makedirs(self.config['output_dir'], exist_ok=True)
        
    def setup_logging(self):
        """Configure logging based on verbosity settings."""
        if self.config.get('quiet', False):
            logging.getLogger().setLevel(logging.WARNING)
        elif self.config.get('verbose', False):
            logging.getLogger().setLevel(logging.DEBUG)
    
    def load_expected_tasks(self) -> Tuple[List[str], Dict[str, str]]:
        """Load expected task IDs and passwords from test.jsonl file."""
        jsonl_path = self.config['jsonl_path']
        
        # Resolve jsonl_path if relative
        if not Path(jsonl_path).is_absolute():
            current_dir = Path.cwd()
            project_root = None
            
            for parent in [current_dir] + list(current_dir.parents):
                if (parent / "data" / "SentinelBench").exists():
                    project_root = parent
                    break
            
            if project_root:
                jsonl_path_obj = project_root / jsonl_path
            else:
                jsonl_path_obj = Path(jsonl_path)
        else:
            jsonl_path_obj = Path(jsonl_path)
        
        if not jsonl_path_obj.exists():
            logger.error(f"test.jsonl not found at {jsonl_path_obj}")
            return [], {}
        
        tasks: List[str] = []
        task_passwords: Dict[str, str] = {}
        
        with open(jsonl_path_obj, "r") as f:
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
        
        logger.info(f"Loaded {len(tasks)} tasks from test.jsonl")
        return tasks, task_passwords
    
    def filter_tasks(self, tasks: List[str]) -> List[str]:
        """Apply task filtering based on configuration."""
        filtered_tasks = tasks.copy()
        
        # Apply include filter
        if self.config.get('include_tasks'):
            include_list = [t.strip() for t in self.config['include_tasks'].split(',')]
            filtered_tasks = [t for t in filtered_tasks if t in include_list]
        
        # Apply exclude filter
        if self.config.get('exclude_tasks'):
            exclude_list = [t.strip() for t in self.config['exclude_tasks'].split(',')]
            filtered_tasks = [t for t in filtered_tasks if t not in exclude_list]
        
        # Apply regex filter
        if self.config.get('task_filter'):
            pattern = re.compile(self.config['task_filter'])
            filtered_tasks = [t for t in filtered_tasks if pattern.search(t)]
        
        logger.info(f"Filtered tasks: {len(filtered_tasks)}/{len(tasks)} tasks selected")
        return filtered_tasks
    
    def setup_plot_style(self):
        """Set up beautiful, paper-ready plot styling."""
        plt.style.use("default")
        
        # Font settings
        plt.rcParams["font.family"] = "serif"
        plt.rcParams["font.serif"] = [
            "Times", "Computer Modern Roman", "CMU Serif", 
            "Liberation Serif", "DejaVu Serif", "serif"
        ]
        plt.rcParams["font.size"] = 14
        plt.rcParams["axes.labelsize"] = 16
        plt.rcParams["axes.titlesize"] = 18
        plt.rcParams["xtick.labelsize"] = 13
        plt.rcParams["ytick.labelsize"] = 13
        plt.rcParams["legend.fontsize"] = 14
        plt.rcParams["figure.titlesize"] = 20
        
        # High-quality settings
        dpi = self.config.get('plot_dpi', 300)
        plt.rcParams["figure.dpi"] = 150
        plt.rcParams["savefig.dpi"] = dpi
        plt.rcParams["savefig.bbox"] = "tight"
        plt.rcParams["savefig.pad_inches"] = 0.1
        
        # Color scheme
        plt.rcParams["axes.prop_cycle"] = plt.cycler(
            "color", [
                "#9D7FE0", "#B19FE8", "#C5BFF0", "#E8E3F8", "#F5F3FC"
            ]
        )
        
        # Clean appearance
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
        
        # Backgrounds
        plt.rcParams["figure.facecolor"] = "white"
        plt.rcParams["axes.facecolor"] = "#FEFEFE"
    
    def calculate_cost(self, prompt_tokens: int, completion_tokens: int, model: str) -> float:
        """Calculate cost for a task based on token usage and model pricing."""
        cost_model = self.config.get('cost_model_override') or model
        
        if cost_model not in MODEL_PRICING:
            logger.warning(f"Unknown model: {cost_model}. Using gpt-4o pricing as default.")
            cost_model = "gpt-4o"
        
        pricing = MODEL_PRICING[cost_model]
        
        input_cost = (prompt_tokens / 1000) * pricing["input"]
        output_cost = (completion_tokens / 1000) * pricing["output"]
        
        return input_cost + output_cost
    
    def check_run_exists(self, run_dir: Path, task_name: str, dimension: int) -> bool:
        """Check if a run exists (regardless of success/failure)."""
        task_dir = run_dir / task_name / str(dimension)
        
        if not task_dir.exists():
            return False
        
        times_file = task_dir / "times.json"
        score_file = task_dir / "score.json"
        
        return times_file.exists() and score_file.exists()
    
    def check_run_validity(
        self, 
        run_dir: Path, 
        task_name: str, 
        dimension: int, 
        expected_password: str
    ) -> Tuple[bool, bool, str, Optional[float]]:
        """
        Check if a run exists and analyze its status.
        
        Returns:
            (exists, has_timeout, status_message, score)
        """
        task_dir = run_dir / task_name / str(dimension)
        
        if not task_dir.exists():
            return False, False, "Directory missing", None
        
        # Check for required files
        times_file = task_dir / "times.json"
        answer_files = list(task_dir.glob(f"{task_name}_{dimension}_answer.json"))
        tokens_file = task_dir / "model_tokens_usage.json"
        score_file = task_dir / "score.json"
        
        if not times_file.exists():
            return False, False, "times.json missing", None
        
        if not answer_files:
            return False, False, "answer file missing", None
        
        if not tokens_file.exists():
            return False, False, "model_tokens_usage.json missing", None
        
        try:
            # Load timing data
            with open(times_file) as f:
                times_data = json.load(f)
                completed = times_data.get("completed", False)
                interrupted = times_data.get("interrupted", False)
            
            # Load answer data
            with open(answer_files[0]) as f:
                answer_data = json.load(f)
                answer = answer_data.get("answer", "")
            
            # Load score if available
            score = None
            if score_file.exists():
                with open(score_file) as f:
                    score_data = json.load(f)
                    score = score_data.get("score", 0.0)
            
            # Check for timeout
            has_timeout = "TIMEOUT" in answer.upper()
            
            # Determine status based on validation method
            if self.config.get('check_messages', False):
                # Check messages.json for password
                messages_files = list(task_dir.glob(f"{task_name}_{dimension}_messages.json"))
                if messages_files:
                    with open(messages_files[0], "r") as f:
                        messages_content = f.read().upper()
                        expected_full_password = f"{expected_password}_{dimension}".upper()
                        has_correct_password = expected_full_password in messages_content
                else:
                    has_correct_password = False
            else:
                # Check answer.json for exact match
                expected_full_password = f"{expected_password}_{dimension}".upper()
                has_correct_password = answer.upper() == expected_full_password
            
            # Determine final status
            if interrupted:
                status = "interrupted"
            elif not completed:
                status = "not completed"
            elif has_timeout:
                status = "completed with timeout"
            elif has_correct_password:
                status = "completed successfully"
            else:
                status = "completed with failure"
            
            return True, has_timeout, status, score
            
        except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
            return False, False, f"Error reading files: {e}", None
    
    def load_task_data(self, run_dir: str, task_name: str) -> pd.DataFrame:
        """Load task data from run directory for a specific task across all dimensions."""
        data = []
        run_path = Path(run_dir)
        
        task_dirs = [
            d for d in run_path.iterdir() 
            if d.is_dir() and d.name.startswith(task_name)
        ]
        
        if not task_dirs:
            raise ValueError(f"No directories found for task '{task_name}' in {run_dir}")
        
        for task_dir in task_dirs:
            for dim_dir in task_dir.iterdir():
                if not dim_dir.is_dir():
                    continue
                
                try:
                    dimension = int(dim_dir.name)
                except ValueError:
                    continue
                
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
                        task_data["total_tokens"] = (
                            task_data["prompt_tokens"] + task_data["completion_tokens"]
                        )
                else:
                    logger.warning(f"No token usage file found for {task_name} dimension {dimension}")
                    task_data["prompt_tokens"] = 0
                    task_data["completion_tokens"] = 0
                    task_data["total_tokens"] = 0
                
                # Load evaluation score
                score_file = dim_dir / "score.json"
                if score_file.exists():
                    with open(score_file) as f:
                        score_data = json.load(f)
                        task_data["score"] = score_data.get("score", 0.0)
                else:
                    logger.warning(f"No score.json found for {task_name} dimension {dimension}")
                    task_data["score"] = None
                
                # Apply filtering based on configuration
                if self.config.get('require_success', False):
                    if task_data.get("score", 0) < self.config.get('score_threshold', 1.0):
                        continue
                
                if not self.config.get('include_timeouts', True):
                    if "TIMEOUT" in task_data.get("answer", "").upper():
                        continue
                
                if not self.config.get('include_failures', True):
                    if task_data.get("score", 0) == 0:
                        continue
                
                data.append(task_data)
        
        if not data:
            raise ValueError(f"No valid data found for task '{task_name}'")
        
        df = pd.DataFrame(data)
        df = df.sort_values("dimension")
        
        logger.info(f"Loaded data for {len(df)} dimension variants of task '{task_name}'")
        return df
    
    def save_plot(self, fig: Any, base_path: str, suffix: str = ""):
        """Save plot in configured format(s)."""
        if self.config.get('no_plots', False):
            plt.close(fig)
            return
        
        plot_format = self.config.get('plot_format', 'both')
        
        if suffix:
            plot_path = base_path.replace('.png', f'_{suffix}.png')
        else:
            plot_path = base_path
        
        if plot_format in ['png', 'both']:
            fig.savefig(plot_path, dpi=self.config.get('plot_dpi', 300), bbox_inches='tight')
        
        if plot_format in ['pdf', 'both']:
            pdf_path = plot_path.replace('.png', '.pdf')
            fig.savefig(pdf_path, dpi=self.config.get('plot_dpi', 300), bbox_inches='tight')
        
        plt.close(fig)
        logger.info(f"Plot saved: {plot_path}")

    # =====================================================================
    # MISSING RUNS ANALYSIS
    # =====================================================================
    
    def analyze_missing_runs(self):
        """Check for missing runs and generate comprehensive report."""
        logger.info("🔍 Starting missing runs analysis...")
        
        base_path_obj = Path(self.config['base_path'])
        directories = self.config.get('directories', ['0', '1'])
        
        expected_tasks, task_passwords = self.load_expected_tasks()
        expected_tasks = self.filter_tasks(expected_tasks)
        
        if not expected_tasks:
            logger.error("No tasks to analyze after filtering")
            return
        
        total_expected = 0
        total_found = 0
        total_missing = 0
        total_timeouts = 0
        all_missing_runs: List[str] = []
        timeout_stats: Dict[str, Dict[str, int]] = {}
        
        print("\n" + "=" * 80)
        print("SENTINELBENCH RUN STATUS REPORT")
        print("=" * 80)
        
        for directory in directories:
            run_dir = base_path_obj / directory
            
            print(f"\n📁 Directory: {directory}")
            print("-" * 50)
            
            dir_expected = 0
            dir_found = 0
            dir_missing = 0
            dir_timeouts = 0
            dir_missing_runs: List[str] = []
            
            for task_name in expected_tasks:
                if task_name not in SENTINELBENCH_TASK_VARIANTS:
                    logger.warning(f"Task '{task_name}' not in expected dimensions. Skipping.")
                    continue
                
                expected_dims = SENTINELBENCH_TASK_VARIANTS[task_name]
                expected_password = task_passwords.get(task_name, "")
                
                # Apply custom dimensions if specified
                if self.config.get('custom_dimensions'):
                    expected_dims = [int(d) for d in self.config['custom_dimensions'].split(',')]
                
                for dimension in expected_dims:
                    dir_expected += 1
                    total_expected += 1
                    
                    exists, has_timeout, status, score = self.check_run_validity(
                        run_dir, task_name, dimension, expected_password
                    )
                    
                    if exists:
                        dir_found += 1
                        total_found += 1
                        
                        if has_timeout:
                            dir_timeouts += 1
                            total_timeouts += 1
                            
                            if task_name not in timeout_stats:
                                timeout_stats[task_name] = {}
                            if directory not in timeout_stats[task_name]:
                                timeout_stats[task_name][directory] = 0
                            timeout_stats[task_name][directory] += 1
                    else:
                        dir_missing += 1
                        total_missing += 1
                        missing_run = f"{directory}/{task_name}/{dimension}"
                        dir_missing_runs.append(missing_run)
                        all_missing_runs.append(missing_run)
            
            # Print directory summary
            completion_rate = (dir_found / dir_expected * 100) if dir_expected > 0 else 0
            timeout_rate = (dir_timeouts / dir_found * 100) if dir_found > 0 else 0
            
            print(f"Expected runs: {dir_expected}")
            print(f"Found runs: {dir_found}")
            print(f"Missing runs: {dir_missing}")
            print(f"Completion rate: {completion_rate:.1f}%")
            print(f"Runs with timeouts: {dir_timeouts} ({timeout_rate:.1f}% of found runs)")
            
            if dir_missing_runs and not self.config.get('quiet', False):
                print(f"\nMissing runs in directory {directory}:")
                for missing_run in sorted(dir_missing_runs)[:10]:  # Limit output
                    print(f"  ❌ {missing_run}")
                if len(dir_missing_runs) > 10:
                    print(f"  ... and {len(dir_missing_runs) - 10} more")
        
        # Overall summary
        print("\n" + "=" * 80)
        print("OVERALL SUMMARY")
        print("=" * 80)
        
        overall_completion = (total_found / total_expected * 100) if total_expected > 0 else 0
        overall_timeout_rate = (total_timeouts / total_found * 100) if total_found > 0 else 0
        
        print(f"Total expected runs: {total_expected}")
        print(f"Total found runs: {total_found}")
        print(f"Total missing runs: {total_missing}")
        print(f"Overall completion rate: {overall_completion:.1f}%")
        print(f"Total runs with timeouts: {total_timeouts} ({overall_timeout_rate:.1f}% of found runs)")
        
        # Save summary to file
        if self.config.get('save_csv', False):
            summary_path = os.path.join(self.config['output_dir'], "missing_runs_summary.json")
            summary_data = {
                "total_expected": total_expected,
                "total_found": total_found,
                "total_missing": total_missing,
                "total_timeouts": total_timeouts,
                "overall_completion_rate": overall_completion,
                "overall_timeout_rate": overall_timeout_rate,
                "missing_runs": all_missing_runs,
                "timeout_stats": timeout_stats
            }
            
            with open(summary_path, 'w') as f:
                json.dump(summary_data, f, indent=2)
            
            logger.info(f"Missing runs summary saved to {summary_path}")

    # =====================================================================
    # SINGLE TASK ANALYSIS
    # =====================================================================
    
    def analyze_single_task(self, task_name: str):
        """Analyze a single task across all dimensions."""
        logger.info(f"🎯 Analyzing single task: {task_name}")
        
        # Use first directory as the main directory for single task analysis
        main_dir = os.path.join(self.config['base_path'], self.config['directories'][0])
        
        try:
            df = self.load_task_data(main_dir, task_name)
        except ValueError as e:
            logger.error(f"Failed to load data for {task_name}: {e}")
            return
        
        if len(df) == 0:
            logger.error(f"No data found for task {task_name}")
            return
        
        # Add cost column
        df['cost'] = df.apply(
            lambda row: self.calculate_cost(
                row['prompt_tokens'], row['completion_tokens'], self.config['model']
            ), axis=1
        )
        
        # Save CSV if requested
        if self.config.get('save_csv', False):
            csv_path = os.path.join(
                self.config['output_dir'], 
                f"{task_name.replace('/', '_')}_analysis.csv"
            )
            df.to_csv(csv_path, index=False)
            logger.info(f"Task data saved to {csv_path}")
        
        # Generate plots
        if not self.config.get('no_plots', False):
            base_path = os.path.join(
                self.config['output_dir'], 
                f"{task_name.replace('/', '_')}.png"
            )
            
            if self.config.get('save_combined_plots', True):
                fig = self.create_combined_single_task_plot(df, task_name)
                self.save_plot(fig, base_path, "combined")
            
            if self.config.get('save_individual_plots', False):
                # Individual metric plots
                fig_acc = self.create_accuracy_plot(df, task_name)
                self.save_plot(fig_acc, base_path, "accuracy")
                
                fig_lat = self.create_latency_plot(df, task_name)
                self.save_plot(fig_lat, base_path, "latency")
                
                fig_cost = self.create_cost_plot(df, task_name)
                self.save_plot(fig_cost, base_path, "cost")
        
        # Print summary
        if not self.config.get('quiet', False):
            self.print_single_task_summary(df, task_name)

    # =====================================================================
    # FULL DIRECTORY ANALYSIS
    # =====================================================================
    
    def analyze_full_directory(self):
        """Analyze all tasks in a single directory."""
        logger.info("📊 Starting full directory analysis...")
        
        expected_tasks, _ = self.load_expected_tasks()
        expected_tasks = self.filter_tasks(expected_tasks)
        
        if not expected_tasks:
            logger.error("No tasks to analyze after filtering")
            return
        
        # Use first directory as the main directory for full analysis
        main_dir = os.path.join(self.config['base_path'], self.config['directories'][0])
        all_task_data = []
        successful_tasks = []
        
        # Analyze each task
        if self.config.get('parallel', False):
            # Parallel processing
            with ThreadPoolExecutor(max_workers=4) as executor:
                future_to_task = {
                    executor.submit(self.load_task_data, main_dir, task): task 
                    for task in expected_tasks
                }
                
                for future in as_completed(future_to_task):
                    task = future_to_task[future]
                    try:
                        df = future.result()
                        df['task_id'] = task
                        all_task_data.append(df)
                        successful_tasks.append(task)
                        logger.info(f"✅ Loaded data for {task}")
                    except Exception as e:
                        logger.warning(f"❌ Failed to load {task}: {e}")
        else:
            # Sequential processing
            for task in expected_tasks:
                try:
                    df = self.load_task_data(main_dir, task)
                    df['task_id'] = task
                    all_task_data.append(df)
                    successful_tasks.append(task)
                    logger.info(f"✅ Loaded data for {task}")
                except Exception as e:
                    logger.warning(f"❌ Failed to load {task}: {e}")
        
        if not all_task_data:
            logger.error("No task data could be loaded")
            return
        
        # Combine all data
        combined_df = pd.concat(all_task_data, ignore_index=True)
        
        # Add cost column
        combined_df['cost'] = combined_df.apply(
            lambda row: self.calculate_cost(
                row['prompt_tokens'], row['completion_tokens'], self.config['model']
            ), axis=1
        )
        
        # Save combined CSV
        if self.config.get('save_csv', False):
            csv_path = os.path.join(
                self.config['output_dir'], 
                f"all_tasks_{self.config['directories'][0]}_analysis.csv"
            )
            combined_df.to_csv(csv_path, index=False)
            logger.info(f"Combined data saved to {csv_path}")
        
        # Generate overall summary
        if not self.config.get('quiet', False):
            self.print_directory_summary(combined_df, successful_tasks)
        
        # Task type analysis if requested
        if self.config.get('task_type_analysis', False):
            self.analyze_task_types_single(combined_df)

    # =====================================================================
    # COMPARISON ANALYSIS
    # =====================================================================
    
    def analyze_comparison(self):
        """Compare multiple directories (2 or more)."""
        directories = self.config['directories']
        labels = self.config['labels']
        
        if len(directories) < 2:
            logger.error("❌ Comparison analysis requires at least 2 directories")
            return
            
        logger.info(f"⚖️ Starting comparison analysis for {len(directories)} directories...")
        
        expected_tasks, _ = self.load_expected_tasks()
        expected_tasks = self.filter_tasks(expected_tasks)
        
        if not expected_tasks:
            logger.error("No tasks to analyze after filtering")
            return
        
        # Build directory paths
        directory_paths = [
            os.path.join(self.config['base_path'], dir_name) 
            for dir_name in directories
        ]
        
        # Store data for each directory
        all_directory_data = {i: [] for i in range(len(directories))}
        successful_tasks = []
        
        # Load data for each task across all directories
        for task in expected_tasks:
            task_data = {}
            
            # Load data from each directory
            for i, (dir_path, label) in enumerate(zip(directory_paths, labels)):
                try:
                    df = self.load_task_data(dir_path, task)
                    df['task_id'] = task
                    df['run_type'] = label
                    df['directory_index'] = i
                    task_data[i] = df
                except Exception as e:
                    logger.warning(f"Failed to load {task} from {label} ({directories[i]}): {e}")
                    task_data[i] = None
            
            # Apply dimension alignment across all directories that have data
            valid_dataframes = {i: df for i, df in task_data.items() if df is not None}
            
            if len(valid_dataframes) >= 2:
                # Apply pairwise alignment across all valid dataframes
                aligned_dfs = list(valid_dataframes.values())
                if len(aligned_dfs) > 1:
                    # For simplicity, align all to the first valid dataframe
                    base_df = aligned_dfs[0]
                    for i, df in enumerate(aligned_dfs[1:], 1):
                        base_df, aligned_dfs[i] = self.align_dimensions(base_df, df, task)
                    
                    # Update the task_data with aligned dataframes
                    valid_indices = list(valid_dataframes.keys())
                    for i, df in enumerate(aligned_dfs):
                        task_data[valid_indices[i]] = df
            
            # Add valid data to collections
            has_valid_data = False
            for i, df in task_data.items():
                if df is not None and len(df) > 0:
                    all_directory_data[i].append(df)
                    has_valid_data = True
            
            if has_valid_data:
                successful_tasks.append(task)
                logger.info(f"✅ Loaded comparison data for {task}")
        
        # Check if we have any data
        if not any(all_directory_data.values()):
            logger.error("No comparison data could be loaded")
            return
        
        # Combine data for each directory
        combined_data = {}
        for i in range(len(directories)):
            if all_directory_data[i]:
                combined_df = pd.concat(all_directory_data[i], ignore_index=True)
                # Add cost column
                combined_df['cost'] = combined_df.apply(
                    lambda row: self.calculate_cost(
                        row['prompt_tokens'], row['completion_tokens'], self.config['model']
                    ), axis=1
                )
                combined_data[i] = combined_df
            else:
                combined_data[i] = pd.DataFrame()
        
        # Save CSVs
        if self.config.get('save_csv', False):
            for i, df in combined_data.items():
                if len(df) > 0:
                    csv_path = os.path.join(
                        self.config['output_dir'], 
                        f"comparison_{labels[i].lower().replace(' ', '_')}.csv"
                    )
                    df.to_csv(csv_path, index=False)
                    logger.info(f"{labels[i]} data saved to {csv_path}")
        
        # Generate comparison plots and analysis
        valid_data = {i: df for i, df in combined_data.items() if len(df) > 0}
        
        if len(valid_data) >= 2:
            # For backward compatibility, use the first two directories for the main comparison plot
            first_dirs = list(valid_data.keys())[:2]
            main_df = valid_data[first_dirs[0]]
            compare_df = valid_data[first_dirs[1]]
            
            # Overall comparison plot
            if self.config.get('save_combined_plots', True) and not self.config.get('no_plots', False):
                base_path = os.path.join(self.config['output_dir'], "comparison.png")
                fig = self.create_combined_comparison_plot(main_df, compare_df)
                self.save_plot(fig, base_path, "combined")
            
            # Print comparison summary
            if not self.config.get('quiet', False):
                self.print_comparison_summary(main_df, compare_df, successful_tasks)
        
        # Task type comparison analysis
        if self.config.get('task_type_analysis', False) and len(valid_data) >= 2:
            first_dirs = list(valid_data.keys())[:2]
            self.analyze_task_types_comparison(valid_data[first_dirs[0]], valid_data[first_dirs[1]])

    # =====================================================================
    # TASK TYPE ANALYSIS
    # =====================================================================
    
    def analyze_task_types_single(self, df: pd.DataFrame):
        """Analyze task types for single directory."""
        logger.info("🏷️ Analyzing task types (duration vs count)...")
        
        for task_type in ['duration', 'count']:
            filtered_df = self.filter_tasks_by_type(df, task_type)
            
            if len(filtered_df) == 0:
                logger.info(f"No {task_type}-based tasks found")
                continue
            
            # Generate plots
            if not self.config.get('no_plots', False):
                base_path = os.path.join(
                    self.config['output_dir'], 
                    f"task_type_{task_type}.png"
                )
                fig = self.create_task_type_plot(filtered_df, task_type)
                self.save_plot(fig, base_path)
            
            # Print summary
            if not self.config.get('quiet', False):
                self.print_task_type_summary(filtered_df, task_type)
    
    def analyze_task_types_comparison(self, main_df: pd.DataFrame, compare_df: pd.DataFrame):
        """Analyze task types for comparison."""
        logger.info("🏷️ Analyzing task type comparison (duration vs count)...")
        
        for task_type in ['duration', 'count']:
            main_filtered = self.filter_tasks_by_type(main_df, task_type)
            compare_filtered = self.filter_tasks_by_type(compare_df, task_type)
            
            if len(main_filtered) == 0 or len(compare_filtered) == 0:
                logger.info(f"Insufficient data for {task_type}-based task comparison")
                continue
            
            # Generate comparison plots
            if not self.config.get('no_plots', False):
                base_path = os.path.join(
                    self.config['output_dir'], 
                    f"task_type_comparison_{task_type}.png"
                )
                fig = self.create_task_type_comparison_plot(
                    main_filtered, compare_filtered, task_type
                )
                self.save_plot(fig, base_path)
            
            # Print comparison summary
            if not self.config.get('quiet', False):
                self.print_task_type_comparison_summary(
                    main_filtered, compare_filtered, task_type
                )

    # =====================================================================
    # HELPER METHODS
    # =====================================================================
    
    def filter_tasks_by_type(self, df: pd.DataFrame, task_type: str) -> pd.DataFrame:
        """Filter tasks by type (duration or count)."""
        if task_type == "duration":
            patterns = DURATION_TASK_PATTERNS
        elif task_type == "count":
            patterns = COUNT_TASK_PATTERNS
        else:
            raise ValueError(f"Invalid task_type: {task_type}")
        
        # Filter by task name patterns
        if patterns:
            mask = df["task_id"].str.contains("|".join(patterns), na=False)
            filtered_df = df[mask].copy()
        else:
            filtered_df = pd.DataFrame()
        
        logger.info(
            f"Filtered {task_type} tasks: {len(filtered_df)} rows from "
            f"{filtered_df['task_id'].nunique() if len(filtered_df) > 0 else 0} unique tasks"
        )
        
        return filtered_df
    
    def align_dimensions(
        self, 
        main_df: pd.DataFrame, 
        compare_df: pd.DataFrame, 
        task_name: str
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Align dimensions between two dataframes based on configuration."""
        main_dims = set(main_df['dimension'].tolist())
        compare_dims = set(compare_df['dimension'].tolist())
        
        if self.config.get('intersection_only', False):
            # Only keep common dimensions
            common_dims = main_dims & compare_dims
            main_df = main_df[main_df['dimension'].isin(common_dims)]
            compare_df = compare_df[compare_df['dimension'].isin(common_dims)]
            
        elif self.config.get('union_fill', False):
            # Fill missing dimensions with artificial entries
            missing_in_main = compare_dims - main_dims
            missing_in_compare = main_dims - compare_dims
            
            # Create artificial entries for missing dimensions
            if missing_in_main:
                artificial_main = []
                for dim in missing_in_main:
                    artificial_main.append({
                        'task_name': task_name,
                        'task_id': task_name,
                        'dimension': dim,
                        'duration': 0,
                        'completed': False,
                        'interrupted': False,
                        'answer': 'MANUALLYPOPULATED',
                        'prompt_tokens': 0,
                        'completion_tokens': 0,
                        'total_tokens': 0,
                        'score': 0.0,
                        'run_type': self.config['labels'][0]
                    })
                
                artificial_df = pd.DataFrame(artificial_main)
                main_df = pd.concat([main_df, artificial_df], ignore_index=True)
            
            if missing_in_compare:
                artificial_compare = []
                for dim in missing_in_compare:
                    artificial_compare.append({
                        'task_name': task_name,
                        'task_id': task_name,
                        'dimension': dim,
                        'duration': 0,
                        'completed': False,
                        'interrupted': False,
                        'answer': 'MANUALLYPOPULATED',
                        'prompt_tokens': 0,
                        'completion_tokens': 0,
                        'total_tokens': 0,
                        'score': 0.0,
                        'run_type': self.config['labels'][1]
                    })
                
                artificial_df = pd.DataFrame(artificial_compare)
                compare_df = pd.concat([compare_df, artificial_df], ignore_index=True)
        
        return main_df.sort_values('dimension'), compare_df.sort_values('dimension')

    # =====================================================================
    # PLOTTING METHODS
    # =====================================================================
    
    def create_combined_single_task_plot(self, df: pd.DataFrame, task_name: str):
        """Create combined plot for single task analysis."""
        self.setup_plot_style()
        
        # Calculate metrics by dimension
        accuracy_data = df.groupby('dimension').agg({'score': 'mean'}).reset_index()
        accuracy_data['accuracy_rate'] = accuracy_data['score'] * 100
        
        latency_data = df.groupby('dimension').agg({'duration': 'mean'}).reset_index()
        latency_data['duration_min'] = latency_data['duration'] / 60
        
        cost_data = df.groupby('dimension').agg({'cost': 'mean'}).reset_index()
        
        # Create subplots
        fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(20, 6))
        
        dimensions = accuracy_data['dimension']
        x_positions = range(len(dimensions))
        
        # Plot 1: Accuracy
        bars1 = ax1.bar(
            x_positions, accuracy_data['accuracy_rate'],
            color="#B19FE8", alpha=0.85, edgecolor="#7B68C7", linewidth=1.5
        )
        
        for i, (bar, acc) in enumerate(zip(bars1, accuracy_data['accuracy_rate'])):
            height = bar.get_height()
            ax1.text(i, height + 1, f"{acc:.1f}%", ha="center", va="bottom",
                    fontsize=11, fontweight="bold", color="#5A4B7B")
        
        ax1.set_xlabel("Task Dimension", fontweight="bold")
        ax1.set_ylabel("Success Rate (%)", fontweight="bold")
        ax1.set_title("Success Rate", fontweight="bold")
        ax1.set_ylim(0, 105)
        ax1.yaxis.set_major_formatter(PercentFormatter())
        ax1.set_xticks(x_positions)
        ax1.set_xticklabels(dimensions)
        
        # Plot 2: Latency
        bars2 = ax2.bar(
            x_positions, latency_data['duration_min'],
            color="#9D7FE0", alpha=0.85, edgecolor="#6A5ACD", linewidth=1.5
        )
        
        for i, (bar, lat) in enumerate(zip(bars2, latency_data['duration_min'])):
            height = bar.get_height()
            ax2.text(i, height * 1.02, f"{lat:.1f}m", ha="center", va="bottom",
                    fontsize=11, fontweight="bold", color="#5A4B7B")
        
        ax2.set_xlabel("Task Dimension", fontweight="bold")
        ax2.set_ylabel("Duration (minutes)", fontweight="bold")
        ax2.set_title("Task Duration", fontweight="bold")
        ax2.set_xticks(x_positions)
        ax2.set_xticklabels(dimensions)
        
        # Plot 3: Cost
        bars3 = ax3.bar(
            x_positions, cost_data['cost'],
            color="#C5BFF0", alpha=0.85, edgecolor="#8A7CA8", linewidth=1.5
        )
        
        for i, (bar, cost) in enumerate(zip(bars3, cost_data['cost'])):
            height = bar.get_height()
            ax3.text(i, height * 1.02, f"${cost:.3f}", ha="center", va="bottom",
                    fontsize=11, fontweight="bold", color="#5A4B7B")
        
        ax3.set_xlabel("Task Dimension", fontweight="bold")
        ax3.set_ylabel("Cost (USD)", fontweight="bold")
        ax3.set_title(f"Cost ({self.config['model']})", fontweight="bold")
        ax3.set_xticks(x_positions)
        ax3.set_xticklabels(dimensions)
        ax3.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f"${x:.3f}"))
        
        # Overall title
        sentiment_suffix = " (With Sentinel)" if self.config.get('sentinel_mode', False) else ""
        fig.suptitle(
            f'Performance Analysis: {task_name.replace("-", " ").title()}{sentiment_suffix}',
            fontsize=22, fontweight="bold", y=1.05
        )
        
        plt.tight_layout()
        return fig
    
    def create_combined_comparison_plot(self, main_df: pd.DataFrame, compare_df: pd.DataFrame):
        """Create combined comparison plot."""
        self.setup_plot_style()
        
        # Aggregate data by dimension
        main_agg = main_df.groupby('dimension').agg({
            'score': 'mean', 'duration': 'mean', 'cost': 'mean'
        }).reset_index()
        
        compare_agg = compare_df.groupby('dimension').agg({
            'score': 'mean', 'duration': 'mean', 'cost': 'mean'
        }).reset_index()
        
        # Get common dimensions
        common_dims = sorted(set(main_agg['dimension']) & set(compare_agg['dimension']))
        
        # Create subplots
        fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(24, 6))
        
        x = np.arange(len(common_dims))
        width = 0.35
        
        # Prepare data
        main_acc = [main_agg[main_agg['dimension'] == d]['score'].iloc[0] * 100 for d in common_dims]
        compare_acc = [compare_agg[compare_agg['dimension'] == d]['score'].iloc[0] * 100 for d in common_dims]
        
        main_dur = [main_agg[main_agg['dimension'] == d]['duration'].iloc[0] / 60 for d in common_dims]
        compare_dur = [compare_agg[compare_agg['dimension'] == d]['duration'].iloc[0] / 60 for d in common_dims]
        
        main_cost = [main_agg[main_agg['dimension'] == d]['cost'].iloc[0] for d in common_dims]
        compare_cost = [compare_agg[compare_agg['dimension'] == d]['cost'].iloc[0] for d in common_dims]
        
        # Plot 1: Accuracy comparison
        bars1_1 = ax1.bar(x - width/2, main_acc, width, label=self.config['labels'][0],
                         color="#B19FE8", alpha=0.85, edgecolor="#7B68C7", linewidth=1.5)
        bars1_2 = ax1.bar(x + width/2, compare_acc, width, label=self.config['labels'][1],
                         color="#7B68C7", alpha=0.85, edgecolor="#5A4B7B", linewidth=1.5)
        
        ax1.set_xlabel("Task Dimension", fontweight="bold")
        ax1.set_ylabel("Success Rate (%)", fontweight="bold")
        ax1.set_title("Success Rate", fontweight="bold")
        ax1.set_ylim(0, 105)
        ax1.yaxis.set_major_formatter(PercentFormatter())
        ax1.set_xticks(x)
        ax1.set_xticklabels(common_dims)
        ax1.legend()
        
        # Plot 2: Duration comparison
        bars2_1 = ax2.bar(x - width/2, main_dur, width, label=self.config['labels'][0],
                         color="#B19FE8", alpha=0.85, edgecolor="#7B68C7", linewidth=1.5)
        bars2_2 = ax2.bar(x + width/2, compare_dur, width, label=self.config['labels'][1],
                         color="#7B68C7", alpha=0.85, edgecolor="#5A4B7B", linewidth=1.5)
        
        ax2.set_xlabel("Task Dimension", fontweight="bold")
        ax2.set_ylabel("Duration (minutes)", fontweight="bold")
        ax2.set_title("Task Duration", fontweight="bold")
        ax2.set_xticks(x)
        ax2.set_xticklabels(common_dims)
        ax2.legend()
        
        # Plot 3: Cost comparison
        bars3_1 = ax3.bar(x - width/2, main_cost, width, label=self.config['labels'][0],
                         color="#B19FE8", alpha=0.85, edgecolor="#7B68C7", linewidth=1.5)
        bars3_2 = ax3.bar(x + width/2, compare_cost, width, label=self.config['labels'][1],
                         color="#7B68C7", alpha=0.85, edgecolor="#5A4B7B", linewidth=1.5)
        
        ax3.set_xlabel("Task Dimension", fontweight="bold")
        ax3.set_ylabel("Cost (USD)", fontweight="bold")
        ax3.set_title(f"Cost ({self.config['model']})", fontweight="bold")
        ax3.set_xticks(x)
        ax3.set_xticklabels(common_dims)
        ax3.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f"${x:.3f}"))
        ax3.legend()
        
        # Overall title
        fig.suptitle("Performance Comparison Analysis", fontsize=22, fontweight="bold", y=1.05)
        
        plt.tight_layout()
        return fig
    
    def create_accuracy_plot(self, df: pd.DataFrame, task_name: str):
        """Create individual accuracy plot."""
        self.setup_plot_style()
        
        accuracy_data = df.groupby('dimension').agg({'score': 'mean'}).reset_index()
        accuracy_data['accuracy_rate'] = accuracy_data['score'] * 100
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        dimensions = accuracy_data['dimension']
        x_positions = range(len(dimensions))
        
        bars = ax.bar(x_positions, accuracy_data['accuracy_rate'],
                     color="#B19FE8", alpha=0.85, edgecolor="#7B68C7", linewidth=1.5)
        
        for i, (bar, acc) in enumerate(zip(bars, accuracy_data['accuracy_rate'])):
            height = bar.get_height()
            ax.text(i, height + 1, f"{acc:.1f}%", ha="center", va="bottom",
                   fontsize=12, fontweight="bold", color="#5A4B7B")
        
        ax.set_xlabel("Task Dimension", fontweight="bold")
        ax.set_ylabel("Success Rate (%)", fontweight="bold")
        ax.set_title(f'Success Rate: {task_name.replace("-", " ").title()}', fontweight="bold")
        ax.set_ylim(0, 105)
        ax.yaxis.set_major_formatter(PercentFormatter())
        ax.set_xticks(x_positions)
        ax.set_xticklabels(dimensions)
        
        plt.tight_layout()
        return fig
    
    def create_latency_plot(self, df: pd.DataFrame, task_name: str):
        """Create individual latency plot."""
        self.setup_plot_style()
        
        latency_data = df.groupby('dimension').agg({'duration': 'mean'}).reset_index()
        latency_data['duration_min'] = latency_data['duration'] / 60
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        dimensions = latency_data['dimension']
        x_positions = range(len(dimensions))
        
        bars = ax.bar(x_positions, latency_data['duration_min'],
                     color="#9D7FE0", alpha=0.85, edgecolor="#6A5ACD", linewidth=1.5)
        
        for i, (bar, lat) in enumerate(zip(bars, latency_data['duration_min'])):
            height = bar.get_height()
            ax.text(i, height * 1.02, f"{lat:.1f}m", ha="center", va="bottom",
                   fontsize=12, fontweight="bold", color="#5A4B7B")
        
        ax.set_xlabel("Task Dimension", fontweight="bold")
        ax.set_ylabel("Duration (minutes)", fontweight="bold")
        ax.set_title(f'Duration: {task_name.replace("-", " ").title()}', fontweight="bold")
        ax.set_xticks(x_positions)
        ax.set_xticklabels(dimensions)
        
        plt.tight_layout()
        return fig
    
    def create_cost_plot(self, df: pd.DataFrame, task_name: str):
        """Create individual cost plot."""
        self.setup_plot_style()
        
        cost_data = df.groupby('dimension').agg({'cost': 'mean'}).reset_index()
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        dimensions = cost_data['dimension']
        x_positions = range(len(dimensions))
        
        bars = ax.bar(x_positions, cost_data['cost'],
                     color="#C5BFF0", alpha=0.85, edgecolor="#8A7CA8", linewidth=1.5)
        
        for i, (bar, cost) in enumerate(zip(bars, cost_data['cost'])):
            height = bar.get_height()
            ax.text(i, height * 1.02, f"${cost:.3f}", ha="center", va="bottom",
                   fontsize=12, fontweight="bold", color="#5A4B7B")
        
        ax.set_xlabel("Task Dimension", fontweight="bold")
        ax.set_ylabel("Cost (USD)", fontweight="bold")
        ax.set_title(f'Cost: {task_name.replace("-", " ").title()} ({self.config["model"]})', 
                    fontweight="bold")
        ax.set_xticks(x_positions)
        ax.set_xticklabels(dimensions)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f"${x:.3f}"))
        
        plt.tight_layout()
        return fig
    
    def create_task_type_plot(self, df: pd.DataFrame, task_type: str):
        """Create task type analysis plot."""
        # Aggregate by dimension across all tasks of this type
        agg_data = df.groupby('dimension').agg({
            'score': 'mean', 'duration': 'mean', 'cost': 'mean'
        }).reset_index()
        
        return self.create_combined_single_task_plot(df, f"{task_type.title()}-Based Tasks")
    
    def create_task_type_comparison_plot(self, main_df: pd.DataFrame, compare_df: pd.DataFrame, task_type: str):
        """Create task type comparison plot."""
        return self.create_combined_comparison_plot(main_df, compare_df)

    # =====================================================================
    # SUMMARY METHODS
    # =====================================================================
    
    def print_single_task_summary(self, df: pd.DataFrame, task_name: str):
        """Print summary statistics for single task analysis."""
        print("\n" + "=" * 80)
        print(f"TASK ANALYSIS: {task_name.replace('-', ' ').title()}")
        print("=" * 80)
        
        dimensions = sorted(df['dimension'].unique())
        print(f"Dimensions analyzed: {dimensions}")
        print(f"Total runs: {len(df)}")
        print(f"Model: {self.config['model']}")
        
        # Per-dimension statistics
        print(f"\n{'Dimension':<10} {'Success Rate':<12} {'Avg Duration':<15} {'Avg Cost':<10}")
        print("-" * 50)
        
        for dim in dimensions:
            dim_data = df[df['dimension'] == dim]
            success_rate = dim_data['score'].mean() * 100
            avg_duration = dim_data['duration'].mean() / 60
            avg_cost = dim_data['cost'].mean()
            
            print(f"{dim:<10} {success_rate:<11.1f}% {avg_duration:<14.1f}m ${avg_cost:<9.3f}")
        
        # Overall statistics
        print(f"\nOverall Statistics:")
        print(f"  Average success rate: {df['score'].mean() * 100:.1f}%")
        print(f"  Average duration: {df['duration'].mean() / 60:.1f} minutes")
        print(f"  Average cost: ${df['cost'].mean():.3f}")
        print(f"  Total cost: ${df['cost'].sum():.3f}")
        print(f"  Total tokens: {df['total_tokens'].sum():,}")
    
    def print_directory_summary(self, df: pd.DataFrame, successful_tasks: List[str]):
        """Print summary for full directory analysis."""
        print("\n" + "=" * 80)
        print(f"DIRECTORY ANALYSIS: {self.config['directories'][0]}")
        print("=" * 80)
        
        print(f"Successfully analyzed tasks: {len(successful_tasks)}")
        print(f"Total runs: {len(df)}")
        print(f"Tasks: {', '.join(successful_tasks[:10])}{'...' if len(successful_tasks) > 10 else ''}")
        
        # Overall metrics
        overall_success = df['score'].mean() * 100
        overall_duration = df['duration'].mean() / 60
        overall_cost = df['cost'].mean()
        total_cost = df['cost'].sum()
        
        print(f"\nOverall Performance:")
        print(f"  Average success rate: {overall_success:.1f}%")
        print(f"  Average duration: {overall_duration:.1f} minutes")
        print(f"  Average cost per run: ${overall_cost:.3f}")
        print(f"  Total cost: ${total_cost:.3f}")
        print(f"  Total tokens: {df['total_tokens'].sum():,}")
        
        # Task breakdown
        task_summary = df.groupby('task_id').agg({
            'score': 'mean', 'duration': 'mean', 'cost': 'sum'
        }).round(3)
        task_summary['success_rate'] = task_summary['score'] * 100
        task_summary['duration_min'] = task_summary['duration'] / 60
        
        print(f"\nTop performing tasks (by success rate):")
        top_tasks = task_summary.nlargest(5, 'success_rate')
        for task, row in top_tasks.iterrows():
            print(f"  {task}: {row['success_rate']:.1f}% success, {row['duration_min']:.1f}m avg, ${row['cost']:.3f} total")
    
    def print_comparison_summary(self, main_df: pd.DataFrame, compare_df: pd.DataFrame, successful_tasks: List[str]):
        """Print comparison summary statistics."""
        print("\n" + "=" * 100)
        print(f"COMPARISON ANALYSIS")
        print(f"{self.config['labels'][0]} vs {self.config['labels'][1]}")
        print("=" * 100)
        
        print(f"Successfully compared tasks: {len(successful_tasks)}")
        print(f"Runs: {self.config['labels'][0]}: {len(main_df)}, {self.config['labels'][1]}: {len(compare_df)}")
        
        # Overall comparison
        main_success = main_df['score'].mean() * 100
        compare_success = compare_df['score'].mean() * 100
        success_diff = main_success - compare_success
        
        main_duration = main_df['duration'].mean() / 60
        compare_duration = compare_df['duration'].mean() / 60
        duration_diff = main_duration - compare_duration
        
        main_cost = main_df['cost'].mean()
        compare_cost = compare_df['cost'].mean()
        cost_diff = main_cost - compare_cost
        
        print(f"\n{'Metric':<20} {self.config['labels'][0]:<20} {self.config['labels'][1]:<20} {'Difference':<15}")
        print("-" * 80)
        print(f"{'Success Rate':<20} {main_success:<19.1f}% {compare_success:<19.1f}% {success_diff:+.1f}%")
        print(f"{'Avg Duration':<20} {main_duration:<19.1f}m {compare_duration:<19.1f}m {duration_diff:+.1f}m")
        print(f"{'Avg Cost':<20} ${main_cost:<18.3f} ${compare_cost:<18.3f} ${cost_diff:+.3f}")
        
        # Winner summary
        print("\n🏆 Performance Summary:")
        if success_diff > 0:
            print(f"   Success: {self.config['labels'][0]} wins by {success_diff:.1f} percentage points")
        elif success_diff < 0:
            print(f"   Success: {self.config['labels'][1]} wins by {abs(success_diff):.1f} percentage points")
        else:
            print("   Success: Tie")
        
        if duration_diff < 0:
            print(f"   Speed: {self.config['labels'][0]} is faster by {abs(duration_diff):.1f} minutes")
        elif duration_diff > 0:
            print(f"   Speed: {self.config['labels'][1]} is faster by {duration_diff:.1f} minutes")
        else:
            print("   Speed: Tie")
        
        if cost_diff < 0:
            print(f"   Cost: {self.config['labels'][0]} is cheaper by ${abs(cost_diff):.3f}")
        elif cost_diff > 0:
            print(f"   Cost: {self.config['labels'][1]} is cheaper by ${cost_diff:.3f}")
        else:
            print("   Cost: Tie")
    
    def print_task_type_summary(self, df: pd.DataFrame, task_type: str):
        """Print task type analysis summary."""
        print(f"\n{task_type.title()}-Based Tasks Analysis:")
        print(f"  Tasks: {df['task_id'].nunique()}")
        print(f"  Runs: {len(df)}")
        print(f"  Avg Success Rate: {df['score'].mean() * 100:.1f}%")
        print(f"  Avg Duration: {df['duration'].mean() / 60:.1f} minutes")
        print(f"  Avg Cost: ${df['cost'].mean():.3f}")
    
    def print_task_type_comparison_summary(self, main_df: pd.DataFrame, compare_df: pd.DataFrame, task_type: str):
        """Print task type comparison summary."""
        print(f"\n{task_type.title()}-Based Tasks Comparison:")
        
        main_success = main_df['score'].mean() * 100
        compare_success = compare_df['score'].mean() * 100
        success_diff = main_success - compare_success
        
        main_duration = main_df['duration'].mean() / 60
        compare_duration = compare_df['duration'].mean() / 60
        duration_diff = main_duration - compare_duration
        
        main_cost = main_df['cost'].mean()
        compare_cost = compare_df['cost'].mean()
        cost_diff = main_cost - compare_cost
        
        print(f"  Success: {self.config['labels'][0]}: {main_success:.1f}%, {self.config['labels'][1]}: {compare_success:.1f}% (diff: {success_diff:+.1f}%)")
        print(f"  Duration: {self.config['labels'][0]}: {main_duration:.1f}m, {self.config['labels'][1]}: {compare_duration:.1f}m (diff: {duration_diff:+.1f}m)")
        print(f"  Cost: {self.config['labels'][0]}: ${main_cost:.3f}, {self.config['labels'][1]}: ${compare_cost:.3f} (diff: ${cost_diff:+.3f})")


# =====================================================================
# CLI COMMAND DEFINITION
# =====================================================================

@app.command()
def main(
    # === CORE CONFIGURATION ===
    model: Annotated[str, typer.Option(
        help="🤖 Model name for cost calculation (e.g., gpt-5-mini, gpt-4o)",
        rich_help_panel="🎯 Core Configuration"
    )],
    output_dir: Annotated[str, typer.Option(
        help="📁 Directory to save all outputs",
        rich_help_panel="🎯 Core Configuration"
    )] = "plots/analysis",
    jsonl_path: Annotated[str, typer.Option(
        help="📄 Path to test.jsonl file with task definitions",
        rich_help_panel="🎯 Core Configuration"
    )] = "data/SentinelBench/test.jsonl",
    base_path: Annotated[str, typer.Option(
        help="📁 Base path where run directories are located",
        rich_help_panel="🎯 Core Configuration"
    )] = "runs/MagenticUI_web_surfer_only/SentinelBench/test",
    
    # === QUICK START OPTIONS ===
    quick_check: Annotated[bool, typer.Option(
        help="⚡ Fast missing runs check only",
        rich_help_panel="🚀 Quick Start"
    )] = False,
    full_comparison: Annotated[bool, typer.Option(
        help="🏆 Complete comparison analysis (with vs without sentinel)",
        rich_help_panel="🚀 Quick Start"
    )] = False,
    single_comprehensive: Annotated[bool, typer.Option(
        help="📊 Full analysis of single directory (all tasks + task types)",
        rich_help_panel="🚀 Quick Start"
    )] = False,
    all_analysis: Annotated[bool, typer.Option(
        help="🎯 Run ALL analysis types (comprehensive evaluation)",
        rich_help_panel="🚀 Quick Start"
    )] = False,
    
    # === ANALYSIS TYPES ===
    single_task_analysis: Annotated[bool, typer.Option(
        help="🎯 Analyze single task across dimensions (requires --task-name)",
        rich_help_panel="📊 Analysis Types"
    )] = False,
    full_directory_analysis: Annotated[bool, typer.Option(
        help="📂 Analyze all tasks in one directory",
        rich_help_panel="📊 Analysis Types"
    )] = False,
    comparison_analysis: Annotated[bool, typer.Option(
        help="⚖️ Compare two directories (with vs without sentinel)",
        rich_help_panel="📊 Analysis Types"
    )] = False,
    missing_runs_check: Annotated[bool, typer.Option(
        help="🔍 Check for missing/failed runs and report statistics",
        rich_help_panel="📊 Analysis Types"
    )] = False,
    task_type_analysis: Annotated[bool, typer.Option(
        help="🏷️ Analyze by task type (duration vs count based)",
        rich_help_panel="📊 Analysis Types"
    )] = False,
    
    # === DIRECTORY SELECTION ===
    directories: Annotated[str, typer.Option(
        help="📁 Space-separated list of directories to analyze (e.g., '0 1 2 3'). First directory is primary, second is comparison.",
        rich_help_panel="📂 Directory Selection"
    )] = "0 1",
    label_names: Annotated[Optional[str], typer.Option(
        help="🏷️ Semicolon-separated list of labels for directories (e.g., 'main; comparison; experimental'). Must match number of directories if provided.",
        rich_help_panel="📂 Directory Selection"
    )] = None,
    
    # === TASK SELECTION ===
    task_name: Annotated[Optional[str], typer.Option(
        help="🎯 Specific task to analyze (required for single-task analysis)",
        rich_help_panel="🔍 Task Selection"
    )] = None,
    task_filter: Annotated[Optional[str], typer.Option(
        help="🔍 Regex pattern to filter tasks (e.g., 'button.*easy')",
        rich_help_panel="🔍 Task Selection"
    )] = None,
    include_tasks: Annotated[Optional[str], typer.Option(
        help="✅ Comma-separated list of tasks to include",
        rich_help_panel="🔍 Task Selection"
    )] = None,
    exclude_tasks: Annotated[Optional[str], typer.Option(
        help="❌ Comma-separated list of tasks to exclude",
        rich_help_panel="🔍 Task Selection"
    )] = None,
    
    # === DIMENSION ALIGNMENT ===
    intersection_only: Annotated[bool, typer.Option(
        help="🔗 Only include dimensions present in BOTH directories (AND operation)",
        rich_help_panel="⚖️ Dimension Alignment"
    )] = False,
    union_fill: Annotated[bool, typer.Option(
        help="🔄 Include ALL dimensions, fill missing with artificial failed entries (UNION operation)",
        rich_help_panel="⚖️ Dimension Alignment"
    )] = False,
    
    # === VALIDATION & FILTERING ===
    check_messages: Annotated[bool, typer.Option(
        help="📝 Use messages.json for password validation (substring search) instead of exact answer match",
        rich_help_panel="🔍 Validation & Filtering"
    )] = False,
    require_success: Annotated[bool, typer.Option(
        help="✅ Only analyze successful runs (exclude failures and timeouts)",
        rich_help_panel="🔍 Validation & Filtering"
    )] = False,
    include_timeouts: Annotated[bool, typer.Option(
        help="⏰ Include runs that timed out in analysis",
        rich_help_panel="🔍 Validation & Filtering"
    )] = True,
    include_failures: Annotated[bool, typer.Option(
        help="💥 Include failed runs in analysis",
        rich_help_panel="🔍 Validation & Filtering"
    )] = True,
    
    # === OUTPUT OPTIONS ===
    save_csv: Annotated[bool, typer.Option(
        help="💾 Save processed data to CSV files",
        rich_help_panel="💾 Output Options"
    )] = False,
    save_individual_plots: Annotated[bool, typer.Option(
        help="📈 Save individual plots for each metric (accuracy, latency, cost)",
        rich_help_panel="💾 Output Options"
    )] = False,
    save_combined_plots: Annotated[bool, typer.Option(
        help="📊 Save combined plots with all metrics",
        rich_help_panel="💾 Output Options"
    )] = True,
    save_summary_only: Annotated[bool, typer.Option(
        help="📄 Only save summary statistics, no plots",
        rich_help_panel="💾 Output Options"
    )] = False,
    output_prefix: Annotated[Optional[str], typer.Option(
        help="🏷️ Prefix for output files (auto-generated if not specified)",
        rich_help_panel="💾 Output Options"
    )] = None,
    
    # === PLOT CUSTOMIZATION ===
    plot_format: Annotated[str, typer.Option(
        help="🎨 Output format for plots (png, pdf, both)",
        rich_help_panel="🎨 Plot Customization"
    )] = "both",
    plot_dpi: Annotated[int, typer.Option(
        help="🔍 DPI for saved plots (higher = better quality)",
        rich_help_panel="🎨 Plot Customization"
    )] = 300,
    no_plots: Annotated[bool, typer.Option(
        help="🚫 Skip plot generation, only generate statistics",
        rich_help_panel="🎨 Plot Customization"
    )] = False,
    
    # === LABELS & DISPLAY ===
    sentinel_mode: Annotated[bool, typer.Option(
        help="🎭 Add sentinel suffix to single-directory analysis titles",
        rich_help_panel="🏷️ Labels & Display"
    )] = False,
    
    # === PERFORMANCE OPTIONS ===
    parallel: Annotated[bool, typer.Option(
        help="⚡ Run individual task analyses in parallel (faster)",
        rich_help_panel="⚙️ Performance"
    )] = False,
    skip_individual: Annotated[bool, typer.Option(
        help="⏩ Skip individual task plots, only generate combined analysis",
        rich_help_panel="⚙️ Performance"
    )] = False,
    verbose: Annotated[bool, typer.Option(
        help="🔊 Detailed logging output (debug information)",
        rich_help_panel="⚙️ Performance"
    )] = False,
    quiet: Annotated[bool, typer.Option(
        help="🔇 Minimal output (errors and warnings only)",
        rich_help_panel="⚙️ Performance"
    )] = False,
    
    # === ADVANCED OPTIONS ===
    custom_dimensions: Annotated[Optional[str], typer.Option(
        help="🔧 Override expected dimensions with custom comma-separated list",
        rich_help_panel="🔧 Advanced Options"
    )] = None,
    cost_model_override: Annotated[Optional[str], typer.Option(
        help="💰 Use different model for cost calculation than main model",
        rich_help_panel="🔧 Advanced Options"
    )] = None,
    timeout_threshold: Annotated[Optional[int], typer.Option(
        help="⏱️ Custom timeout threshold in seconds",
        rich_help_panel="🔧 Advanced Options"
    )] = None,
    score_threshold: Annotated[float, typer.Option(
        help="🎯 Minimum score to consider as success (default: 1.0 = perfect)",
        rich_help_panel="🔧 Advanced Options"
    )] = 1.0,
):
    """
    🚀 **SentinelBench Unified Analyzer**
    
    All-in-one tool for SentinelBench analysis including single task analysis,
    full directory analysis, comparison analysis, missing runs detection, and task type analysis.
    
    **Quick Examples:**
    ```
    # Quick missing runs check
    sentinelbench_analyzer --quick-check --model gpt-5-mini
    
    # Single comprehensive analysis
    sentinelbench_analyzer --single-comprehensive --model gpt-5-mini
    
    # Full comparison analysis
    sentinelbench_analyzer --full-comparison --model gpt-5-mini
    ```
    """
    
    # Validate model
    if model not in MODEL_PRICING:
        typer.echo(f"❌ Invalid model: {model}. Must be one of: {', '.join(MODEL_PRICING.keys())}", err=True)
        raise typer.Exit(1)
    
    # Handle convenience flags
    if quick_check:
        missing_runs_check = True
        quiet = True
    
    if full_comparison:
        comparison_analysis = True
        union_fill = True
        save_csv = True
        save_combined_plots = True
    
    if single_comprehensive:
        full_directory_analysis = True
        save_csv = True
        save_combined_plots = True
        task_type_analysis = True
    
    if all_analysis:
        # Only enable single_task_analysis if task_name is provided
        if task_name:
            single_task_analysis = True
        full_directory_analysis = True
        comparison_analysis = True
        missing_runs_check = True
        task_type_analysis = True
        save_csv = True
        save_combined_plots = True
    
    # Validate analysis selection
    analysis_modes = [
        single_task_analysis, full_directory_analysis, comparison_analysis,
        missing_runs_check, task_type_analysis
    ]
    
    if not any(analysis_modes):
        typer.echo("❌ No analysis mode selected. Use --help to see available options.", err=True)
        raise typer.Exit(1)
    
    # Validate single task analysis requirements
    if single_task_analysis and not task_name:
        typer.echo("❌ --task-name is required for single task analysis", err=True)
        raise typer.Exit(1)
    
    # Validate dimension alignment flags
    if intersection_only and union_fill:
        typer.echo("❌ Cannot use both --intersection-only and --union-fill", err=True)
        raise typer.Exit(1)
    
    if save_summary_only:
        no_plots = True
    
    # Parse directories and labels
    directories_list = directories.split()
    
    # Parse label names if provided
    labels_list = None
    if label_names:
        labels_list = [label.strip() for label in label_names.split(';')]
        if len(labels_list) != len(directories_list):
            typer.echo(f"❌ Number of labels ({len(labels_list)}) must match number of directories ({len(directories_list)})", err=True)
            raise typer.Exit(1)
    else:
        # Generate default labels
        if len(directories_list) == 1:
            labels_list = ["Main"]
        elif len(directories_list) == 2:
            labels_list = ["Main", "Comparison"]
        else:
            labels_list = [f"Dir {i}" for i in directories_list]
    
    # Build configuration
    config = {
        'model': model,
        'output_dir': output_dir,
        'jsonl_path': jsonl_path,
        'base_path': base_path,
        'directories': directories_list,
        'labels': labels_list,
        'task_name': task_name,
        'task_filter': task_filter,
        'include_tasks': include_tasks,
        'exclude_tasks': exclude_tasks,
        'intersection_only': intersection_only,
        'union_fill': union_fill,
        'check_messages': check_messages,
        'require_success': require_success,
        'include_timeouts': include_timeouts,
        'include_failures': include_failures,
        'save_csv': save_csv,
        'save_individual_plots': save_individual_plots,
        'save_combined_plots': save_combined_plots,
        'save_summary_only': save_summary_only,
        'output_prefix': output_prefix,
        'plot_format': plot_format,
        'plot_dpi': plot_dpi,
        'no_plots': no_plots,
        'sentinel_mode': sentinel_mode,
        'parallel': parallel,
        'skip_individual': skip_individual,
        'verbose': verbose,
        'quiet': quiet,
        'custom_dimensions': custom_dimensions,
        'cost_model_override': cost_model_override,
        'timeout_threshold': timeout_threshold,
        'score_threshold': score_threshold,
        'task_type_analysis': task_type_analysis,
    }
    
    # Initialize analyzer
    analyzer = SentinelBenchAnalyzer(config)
    
    # Run selected analyses
    try:
        if not quiet:
            typer.echo("🚀 Starting SentinelBench analysis...")
        
        start_time = time.time()
        
        if missing_runs_check:
            if not quiet:
                typer.echo("🔍 Running missing runs analysis...")
            analyzer.analyze_missing_runs()
        
        if single_task_analysis and task_name:
            if not quiet:
                typer.echo(f"🎯 Running single task analysis for: {task_name}")
            analyzer.analyze_single_task(task_name)
        
        if full_directory_analysis:
            if not quiet:
                typer.echo("📊 Running full directory analysis...")
            analyzer.analyze_full_directory()
        
        if comparison_analysis:
            if not quiet:
                typer.echo("⚖️ Running comparison analysis...")
            analyzer.analyze_comparison()
        
        elapsed_time = time.time() - start_time
        
        if not quiet:
            typer.echo(f"✅ Analysis complete in {elapsed_time:.1f} seconds!")
            typer.echo(f"📂 Results saved to: {output_dir}")
            
    except KeyboardInterrupt:
        typer.echo("\n❌ Analysis interrupted by user", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"❌ Analysis failed: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        raise typer.Exit(1)


if __name__ == "__main__":
    app()