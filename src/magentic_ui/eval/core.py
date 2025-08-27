import os
import logging
import shutil
import multiprocessing
import time
import json
import random
import datetime
from typing import Optional, Union, List, Tuple, Callable
from .benchmark import load_benchmark_class, Benchmark
from .basesystem import load_system_class, BaseSystem
from .models import AllCandidateTypes, AllEvalResultTypes
import traceback


# ----------------------------------------------------------------------
# Setup Logging
# ----------------------------------------------------------------------
def _setup_file_logging(
    runs_dir: str,
    system_name: str,
    benchmark_name: str,
    split: Optional[str],
    run_id: Union[int, List[int]],
    verbose: bool = False,
) -> None:
    """Setup file logging while maintaining console output.

    Args:
        runs_dir (str): Directory to store log file
        system_name (str): Name of the system
        benchmark_name (str): Name of the benchmark
        split (str, optional): Optional dataset split
        run_id (int | List[int]): Run ID or list of run IDs
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_ids = [run_id] if isinstance(run_id, int) else run_id
    run_id_str = "-".join(str(rid) for rid in run_ids)

    log_dir = os.path.join(
        runs_dir,
        "runs",
        system_name,
        benchmark_name,
        split or "all_benchmark",
        str(run_id_str),
    )
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, f"core_eval_{timestamp}.log")

    # Create file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s {%(pathname)s:%(lineno)d} [%(levelname)s] %(name)s - %(message)s"
        )
    )

    # Setup basic config for console output
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s {%(pathname)s:%(lineno)d} [%(levelname)s] %(name)s - %(message)s",
        handlers=[
            logging.StreamHandler(),  # Console handler
            file_handler,  # File handler
        ],
    )


logger = logging.getLogger(__name__)
# Will be set dynamically based on verbose flag
_verbose_mode = False

def set_verbose_logging(verbose: bool):
    """Set verbose logging mode for agent conversations."""
    global _verbose_mode
    _verbose_mode = verbose
    if verbose:
        logging.getLogger("autogen_core").setLevel(logging.INFO)
        logging.getLogger("autogen").setLevel(logging.INFO)
        logging.getLogger("autogen_agentchat").setLevel(logging.INFO)
        logging.getLogger("autogen_agentchat.events").setLevel(logging.INFO)
    else:
        logging.getLogger("autogen_core").setLevel(logging.CRITICAL)
        logging.getLogger("autogen").setLevel(logging.WARNING)
        logging.getLogger("autogen_agentchat").setLevel(logging.WARNING)
        logging.getLogger("autogen_agentchat.events").setLevel(logging.WARNING)

# ----------------------------------------------------------------------
# Type Definitions & Constants
# ----------------------------------------------------------------------
# SystemType represents either a callable that creates a system or a system instance
SystemType = Union[Callable[..., BaseSystem], BaseSystem]
# BenchmarkType represents an optional callable that creates a benchmark
BenchmarkType = Optional[Callable[..., Benchmark]]


# ----------------------------------------------------------------------
# Helper Functions
# ----------------------------------------------------------------------
def _run_single_task(
    system_constructor: Union[Callable[[], BaseSystem], BaseSystem],
    task_id: str,
    output_dir: str,
    reload_system: bool,
    benchmark_constructor: Optional[Union[Callable[..., Benchmark], Benchmark]],
    benchmark_dir: str,
    reload_benchmark: bool,
    benchmark_name: str,
    rerun_timedout: bool = False,
) -> Tuple[str, Optional[AllCandidateTypes], float]:
    """Run a single task in a separate process.

    Args:
        system_constructor (callable | BaseSystem): Callable or BaseSystem instance for creating/using the system
        task_id (str): Unique identifier for the task
        output_dir (str): Directory to store task outputs
        reload_system (bool): Whether to reload system for each task
        benchmark_constructor (callable, optional): Optional callable to create benchmark instance
        benchmark_dir (str): Directory containing benchmark data
        reload_benchmark (bool): Whether to reload benchmark for each task
        benchmark_name (str): Name of the benchmark

    Returns:
        Tuple containing:
            - str: Task identifier
            - Optional[AllCandidateTypes]: System's answer or None if failed
            - float: Time taken in seconds

    The function:
    1. Creates/reuses a system instance based on reload_system flag
    3. Checks for cached results to avoid re-running
    4. Executes the task and measures duration
    5. Saves results and timing information
    """
    logger.info(f"Running task {task_id} in {output_dir}")
    logger.debug(f"_run_single_task called with task_id='{task_id}'")
    logger.debug(f"benchmark_name='{benchmark_name}'")
    
    question_dir = os.path.join(output_dir, str(task_id))
    os.makedirs(question_dir, exist_ok=True)
    logger.debug(f"Created question_dir: {question_dir}")

    try:
        # Initialize or reload system
        if reload_system:
            assert callable(
                system_constructor
            ), "If reload_system is true, system_constructor must be callable"
            system = system_constructor()
        else:
            system = system_constructor

        assert isinstance(system, BaseSystem), "system must be a BaseSystem instance"

        # Initialize or reload benchmark if needed
        if isinstance(benchmark_constructor, Benchmark):
            benchmark = benchmark_constructor
        else:
            benchmark = download_and_load_benchmark(
                benchmark_name, benchmark_dir, benchmark_constructor
            )

        # Load task just before we need it
        logger.debug(f"About to load task with ID: '{task_id}'")
        logger.debug(f"Available tasks in benchmark: {list(benchmark.tasks.keys())[:10]}...")  # Show first 10
        task = benchmark.load_task_by_id(task_id)
        if task is None:
            logger.error(f"[DEBUG] Task '{task_id}' not found in benchmark.tasks")
            logger.error(f"[DEBUG] All available task IDs: {list(benchmark.tasks.keys())}")
            raise ValueError(f"Task {task_id} not found")
        logger.info(f"[DEBUG] Successfully loaded task: id='{task.id}', url_path='{task.url_path}'")

        # If there's already an answer, skip unless it's a timeout
        if os.path.exists(question_dir):
            try:
                existing_answer = system.load_answer_from_disk(task_id, question_dir)
                if existing_answer:
                    # Check if the existing answer is a timeout - if so, rerun the task (if flag is enabled)
                    is_timeout = False
                    if rerun_timedout:
                        if hasattr(existing_answer, 'answer') and isinstance(existing_answer.answer, str):
                            is_timeout = "TIMEOUT: Task execution exceeded time limit" in existing_answer.answer
                        elif isinstance(existing_answer, str):
                            is_timeout = "TIMEOUT: Task execution exceeded time limit" in existing_answer
                    
                    if is_timeout and rerun_timedout:
                        print(f"\033[1;33m🔄 RERUNNING: {task_id} (previous timeout detected)\033[0m")
                        logger.info(f"Rerunning {task_id} (previous result was timeout).")
                        # Clear question directory to start fresh
                        for file in os.listdir(question_dir):
                            file_path = os.path.join(question_dir, file)
                            if os.path.isfile(file_path):
                                os.remove(file_path)
                            elif os.path.isdir(file_path):
                                shutil.rmtree(file_path)
                    else:
                        times_path = os.path.join(question_dir, "times.json")
                        if os.path.exists(times_path):
                            with open(times_path, "r") as f:
                                times_data = json.load(f)
                                # Print prominent green bolded message to console
                                print(f"\033[1;32m✅ SKIPPED: {task_id} (already completed)\033[0m")
                                logger.info(f"Skipping {task_id} (already has answer).")
                                return (
                                    task_id,
                                    existing_answer,
                                    times_data.get("duration", 0),
                                )
                        else:
                            raise FileNotFoundError(f"Times file not found for {task_id}")
            except Exception:
                logger.error(
                    f"Error running task {task_id}: {traceback.format_exc()}.\n Clearing question directory {question_dir}"
                )
                # Clear question directory
                for file in os.listdir(question_dir):
                    file_path = os.path.join(question_dir, file)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)

        # Handle task files if they exist
        if hasattr(task, "file_name") and task.file_name:
            file_path = task.file_name
            if os.path.exists(file_path):
                shutil.copy(
                    file_path, os.path.join(question_dir, os.path.basename(file_path))
                )
            task.file_name = os.path.join(question_dir, os.path.basename(file_path))

        if hasattr(task, "file_dir") and task.file_dir:
            file_dir = task.file_dir
            if os.path.exists(file_dir):
                shutil.copytree(
                    file_dir, os.path.join(question_dir, os.path.basename(file_dir))
                )
            task.file_dir = os.path.join(question_dir, os.path.basename(file_dir))

        start_time = time.time()
        answer = None
        end_time = start_time
        interrupted = False
        
        try:
            answer = system.get_answer(task_id, task, question_dir)
            end_time = time.time()
        except KeyboardInterrupt:
            end_time = time.time()
            interrupted = True
            logger.warning(f"Task {task_id} interrupted by user (Ctrl+C)")
            raise  # Re-raise to maintain expected behavior
        except Exception as e:
            end_time = time.time()
            interrupted = True
            logger.error(f"Task {task_id} failed with exception: {e}")
            
            # Save partial state if the system supports it
            try:
                if hasattr(system, 'save_partial_state'):
                    system.save_partial_state(
                        task_id, 
                        question_dir, 
                        error_message=str(e),
                        error_type=type(e).__name__
                    )
            except Exception as save_error:
                logger.error(f"Failed to save partial state for {task_id}: {save_error}")
            
            # Don't re-raise here - we want to save partial state and continue
        finally:
            # Always save timing data, even for interrupted/failed runs
            times_path = os.path.join(question_dir, "times.json")
            with open(times_path, "w") as f:
                json.dump(
                    {
                        "start_time": start_time,
                        "end_time": end_time,
                        "duration": end_time - start_time,
                        "interrupted": interrupted,
                        "completed": answer is not None,
                    },
                    f,
                )

        logger.info(f"Completed task for task_id={task_id}")
        return task_id, answer, end_time - start_time
    except Exception:
        # Log the error with traceback
        logger.error(f"Error running task {task_id}: {traceback.format_exc()}")
        return task_id, None, 0


# ----------------------------------------------------------------------
# Core Functions
# ----------------------------------------------------------------------
def download_and_load_benchmark(
    benchmark_name: str,
    benchmark_dir: str,
    benchmark_constructor: Optional[Union[Callable[..., Benchmark], Benchmark]] = None,
) -> Benchmark:
    """Load or download benchmark data.

    Args:
        benchmark_name (str): Name of the benchmark
        benchmark_dir (str): Directory to store benchmark data
        benchmark_constructor (callable, optional): Optional callable to create benchmark instance

    Returns:
        Benchmark: Initialized benchmark instance

    The function:
    1. Creates benchmark instance using provided or default constructor
    2. Downloads benchmark data if not present locally
    3. Loads the dataset into memory
    """
    if benchmark_constructor is None:
        benchmark_class = load_benchmark_class(benchmark_name)
        benchmark_constructor = benchmark_class

    if callable(benchmark_constructor):
        data_dir = os.path.join(benchmark_dir, "data", benchmark_name)
        benchmark = benchmark_constructor(name=benchmark_name, data_dir=data_dir)
        
        # Check if we need to download the dataset
        needs_download = False
        if not os.path.exists(data_dir):
            needs_download = True
        else:
            # For WebGames and SentinelBench, check if test.jsonl exists
            if benchmark_name in ["WebGames", "SentinelBench"]:
                test_file = os.path.join(data_dir, "test.jsonl")
                if not os.path.isfile(test_file):
                    needs_download = True
        
        if needs_download:
            logger.info(f"Benchmark data not found in {data_dir}. Downloading...")
            os.makedirs(data_dir, exist_ok=True)
            logger.info(f"Downloading benchmark {benchmark_name} into {data_dir}...")
            benchmark.download_dataset()
            logger.info("Download complete.")
            
        benchmark.load_dataset()
        return benchmark
    else:
        return benchmark_constructor


def run_benchmark_func(
    benchmark_name: str,
    system_name: str,
    parallel: int,
    benchmark_dir: str,
    runs_dir: str,
    split: Optional[str] = None,
    run_id: int = 0,
    benchmark_constructor: Optional[Union[Callable[..., Benchmark], Benchmark]] = None,
    system_constructor: Optional[Union[Callable[..., BaseSystem], BaseSystem]] = None,
    subsample: Optional[float] = None,
    seed: Optional[int] = 42,
    reload_benchmark_per_task: bool = False,
    reload_system_per_task: bool = False,
    task_id: Optional[str] = None,
    base_task: Optional[str] = None,
    difficulty: Optional[str] = None,
    rerun_timedout: bool = False,
    verbose: bool = False,
) -> None:
    """Run benchmark evaluation.

    Args:
        benchmark_name (str): Name of the benchmark
        system_name (str): Name of the system to evaluate
        parallel (int): Number of parallel processes (1 for sequential)
        benchmark_dir (str): Directory containing benchmark data
        runs_dir (str): Directory to store run outputs
        split (str, optional): Optional dataset split to evaluate
        run_id (int, optional): Unique identifier for this run. Default: 0
        benchmark_constructor (Union[Callable[..., BaseSystem] | BaseSystem, optional): Optional callable to create benchmark instance
        system_constructor: Optional callable or instance to create/use system
        subsample (float, optional): Optional fraction (0-1] of tasks to evaluate
        seed (int, optional): Random seed for reproducibility. Default: 42
        reload_benchmark_per_task (bool, optional): Whether to reload benchmark for each task. Default: False
        reload_system_per_task (bool, optional): Whether to reload system for each task. Default: False

    The workflow:
    1. Sets up benchmark and system instances/constructors
    2. Prepares tasks with optional subsampling
    3. Executes tasks in parallel or sequentially
    4. Collects and logs results

    Key features:
    - Supports parallel processing
    - Handles system/benchmark reloading per task
    - Caches results to disk
    - Provides progress logging
    """
    _setup_file_logging(runs_dir, system_name, benchmark_name, split, run_id, verbose)
    set_verbose_logging(verbose)
    if subsample is not None and not (0 < subsample <= 1):
        raise ValueError("subsample must be in the range (0, 1].")
    if seed is not None:
        random.seed(seed)

    # Validate reload_benchmark_per_task with parallel
    if reload_benchmark_per_task and parallel > 1:
        logger.info(
            "reload_benchmark_per_task=True is not supported in parallel mode. Setting to False."
        )
        reload_benchmark_per_task = False

    # Prepare benchmark constructor if needed
    if benchmark_constructor is None and benchmark_name:
        benchmark_class = load_benchmark_class(benchmark_name)
        benchmark_constructor = benchmark_class

    # Load initial benchmark instance
    benchmark = download_and_load_benchmark(
        benchmark_name, benchmark_dir, benchmark_constructor
    )

    output_dir = os.path.join(
        runs_dir,
        "runs",
        system_name,
        benchmark_name,
        split or "all_benchmark",
        str(run_id),
    )
    os.makedirs(output_dir, exist_ok=True)

    # System initialization can be done in three ways:
    # 1. Create new system for each task (reload_system_per_task=True)
    # 2. Reuse provided system instance
    # 3. Create single system instance and reuse
    if system_constructor is None:
        system_class = load_system_class(system_name)
        if reload_system_per_task:

            def create_system():
                return system_class(system_name)

            system_constructor = create_system
        else:
            system = system_class(system_name)
            system_constructor = system
    elif reload_system_per_task and callable(system_constructor):
        # Keep the constructor as is
        pass
    else:
        # Use the provided system directly
        system = system_constructor
        system_constructor = system

    # Get task IDs instead of full tasks
    logger.info(f"[DEBUG] Getting task IDs for split='{split}', benchmark_name='{benchmark_name}'")
    logger.info(f"[DEBUG] Filtering parameters: task_id='{task_id}', base_task='{base_task}', difficulty='{difficulty}'")
    
    if split:
        # For SentinelBench, pass filtering parameters
        if benchmark_name == "SentinelBench":
            logger.info(f"[DEBUG] Calling benchmark.get_split_tasks for SentinelBench")
            task_ids = benchmark.get_split_tasks(split, task_id=task_id, base_task=base_task, difficulty=difficulty)
        else:
            logger.info(f"[DEBUG] Calling benchmark.get_split_tasks for non-SentinelBench")
            task_ids = benchmark.get_split_tasks(split)
    else:
        logger.info(f"[DEBUG] No split specified, using all benchmark tasks")
        task_ids = list(benchmark.tasks.keys())

    logger.info(f"[DEBUG] Before subsample: {len(task_ids)} task IDs: {task_ids}")
    
    if subsample and 0 < subsample <= 1:
        original_count = len(task_ids)
        task_ids = random.sample(task_ids, int(len(task_ids) * subsample))
        logger.info(f"[DEBUG] After subsample ({subsample}): {len(task_ids)} task IDs (reduced from {original_count}): {task_ids}")

    # Task preparation bundles all necessary data for parallel execution
    tasks_system_data = [
        (
            system_constructor,
            task_id,
            output_dir,
            reload_system_per_task,
            benchmark_constructor if reload_benchmark_per_task else benchmark,
            benchmark_dir,
            reload_benchmark_per_task,
            benchmark_name,
            rerun_timedout,
        )
        for task_id in task_ids
    ]

    logger.info(f"[DEBUG] Created {len(tasks_system_data)} task data entries for execution")
    for i, (_, task_id, _, _, _, _, _, _, _) in enumerate(tasks_system_data[:5]):  # Show first 5
        logger.info(f"[DEBUG] Task data [{i}]: task_id='{task_id}'")

    logger.info(
        f"Starting run_benchmark with {'sequential' if parallel == 1 else str(parallel) + ' processes'}..."
    )

    # Separate path for non-parallel execution
    if parallel == 1:
        results: List[Tuple[str, Optional[AllCandidateTypes], float]] = []
        for i, task_data in enumerate(tasks_system_data):
            logger.info(f"[DEBUG] About to execute task {i+1}/{len(tasks_system_data)}: task_id='{task_data[1]}'")
            results.append(_run_single_task(*task_data))
    else:
        with multiprocessing.Pool(processes=parallel) as pool:
            results = pool.starmap(_run_single_task, tasks_system_data)

    success_count = sum(1 for _, answer, _ in results if answer is not None)
    total_time = sum(t for _, a, t in results if a is not None)
    avg_time = total_time / success_count if success_count else 0
    logger.info(f"Average time per successful task: {avg_time:.4f} seconds")

    fail_count = len(results) - success_count

    logger.info(f"Run completed: {success_count} succeeded, {fail_count} failed.")


def _evaluate_single_task(
    task_id: str,
    system: BaseSystem,
    output_dir: str,
    benchmark: Benchmark,
    redo_eval: bool,
) -> Tuple[str, Optional[AllEvalResultTypes], float]:
    """Evaluate a single benchmark task.

    Args:
        task_id (str): Task identifier
        system (BaseSystem): System instance to evaluate
        output_dir (str): Directory containing system outputs
        benchmark (Benchmark): Benchmark instance for evaluation
        redo_eval (bool): Whether to redo evaluation

    Returns:
        Tuple containing:
            - str: Task identifier
            - Optional[AllEvalResultTypes]: Evaluation score or None if failed
            - float: Time taken in seconds

    The function:
    1. Loads the system's answer from disk
    2. Checks for existing evaluation scores
    3. Computes and caches the evaluation score
    4. Returns the score and timing information
    """
    logger.info(f"Evaluating task {task_id} in {output_dir}")
    question_dir = os.path.join(output_dir, str(task_id))
    times_path = os.path.join(question_dir, "times.json")
    score_path = os.path.join(question_dir, "score.json")

    if os.path.exists(times_path):
        with open(times_path, "r") as f:
            times_data = json.load(f)
            duration = times_data.get("duration", 0)
    else:
        duration = -1

    if not redo_eval and os.path.exists(score_path):
        try:
            with open(score_path, "r") as f:
                file_score = json.load(f)
                assert benchmark.eval_result_class is not None
                saved_score = benchmark.eval_result_class.model_validate(file_score)
                logger.info(f"Loaded existing score for {task_id}")
            return (task_id, saved_score, duration)
        except Exception as e:
            logger.info(f"Error loading existing score for {task_id}: {e}")

    # Load task just before evaluation
    task = benchmark.load_task_by_id(task_id)
    if task is None:
        logger.info(f"Task {task_id} not found")
        return (task_id, None, duration)
    try:
        candidate = system.load_answer_from_disk(task_id, question_dir)
    except Exception as e:
        logger.info(f"Error loading candidate for {task_id}: {e}")
        return (task_id, None, duration)
    if candidate is None:
        logger.info(f"No candidate found for {task_id}")
        return (task_id, None, duration)
    logger.info(f"Evaluating candidate for {task_id}")
    score = benchmark.evaluator(task, candidate)
    logger.info(f"Finished evaluating candidate for {task_id} with score {score}")
    with open(score_path, "w") as f:
        json.dump(score.model_dump(), f)
    return (task_id, score, duration)


def evaluate_benchmark_func(
    benchmark_name: str,
    system_name: str,
    benchmark_dir: str,
    runs_dir: str,
    split: Optional[str] = None,
    run_id: Union[int, List[int]] = 0,
    benchmark_constructor: Optional[Union[Callable[..., Benchmark], Benchmark]] = None,
    system_constructor: Optional[Union[Callable[..., BaseSystem], BaseSystem]] = None,
    parallel: int = 1,
    redo_eval: bool = False,
    task_id: Optional[str] = None,
    base_task: Optional[str] = None,
    difficulty: Optional[str] = None,
    verbose: bool = False,
) -> None:
    """Evaluates benchmark results across single or multiple runs.
    Args:
        benchmark_name (str): Name of the benchmark
        system_name (str): Name of the system evaluated
        benchmark_dir (str): Directory containing benchmark data
        runs_dir (str): Directory containing run outputs
        split (str, optional): Optional dataset split that was evaluated
        run_id (int, optional): Run ID or list of run IDs to evaluate. Default: 0
        benchmark_constructor (callable, optional): Optional callable to create benchmark instance
        system_constructor (callable | BaseSystem, optional): Optional callable or instance to create/use system
        parallel (int, optional): Number of parallel processes (1 for sequential). Default: 1
        redo_eval (bool, optional): Whether to redo evaluation even if results exist. Default: False

    The workflow:
    1. Processes each run ID separately
    2. Loads or creates necessary system/benchmark instances
    3. Evaluates all task results
    4. Computes and saves aggregate metrics

    Features:
    - Supports evaluating multiple runs
    - Parallel evaluation processing
    - Caches evaluation scores
    - Computes aggregate metrics across runs
    """
    _setup_file_logging(runs_dir, system_name, benchmark_name, split, run_id, verbose)
    set_verbose_logging(verbose)
    if isinstance(run_id, int):
        run_ids = [run_id]
    else:
        run_ids = run_id

    all_scores: List[List[AllEvalResultTypes]] = []
    all_durations: List[List[float]] = []
    all_quids: List[List[str]] = []
    for rid in run_ids:
        # Prepare benchmark constructor if needed
        if benchmark_constructor is None and benchmark_name:
            benchmark_class = load_benchmark_class(benchmark_name)
            benchmark_constructor = benchmark_class

        benchmark = download_and_load_benchmark(
            benchmark_name, benchmark_dir, benchmark_constructor
        )

        output_dir = os.path.join(
            runs_dir,
            "runs",
            system_name,
            benchmark_name,
            split or "all_benchmark",
            str(rid),
        )
        if not os.path.exists(output_dir):
            raise FileNotFoundError(
                f"No system output found at {output_dir}. Run the benchmark first."
            )

        # Initialize system
        if system_constructor is None:
            system_class = load_system_class(system_name)
            system = system_class(system_name)
        elif callable(system_constructor):
            system = system_constructor()
        else:
            system = system_constructor

        if split:
            # For SentinelBench, pass filtering parameters
            if benchmark_name == "SentinelBench":
                tasks = benchmark.get_split_tasks(split, task_id=task_id, base_task=base_task, difficulty=difficulty)
            else:
                tasks = benchmark.get_split_tasks(split)
        else:
            tasks = benchmark.tasks
        tasks_sys_benchmark_data = [
            (task_id, system, output_dir, benchmark, redo_eval) for task_id in tasks
        ]

        # Separate path for non-parallel execution
        if parallel == 1:
            single_results: List[Tuple[str, Optional[AllEvalResultTypes], float]] = []
            for task_sys_benchmark_data in tasks_sys_benchmark_data:
                single_results.append(_evaluate_single_task(*task_sys_benchmark_data))
        else:
            with multiprocessing.Pool(processes=parallel) as pool:
                single_results = pool.starmap(
                    _evaluate_single_task, tasks_sys_benchmark_data
                )

        # Process single_results in place of the for ex in exs loop
        scores: List[AllEvalResultTypes] = []
        durations: List[float] = []
        quids: List[str] = []
        failed_count = 0
        for qid, score, duration in single_results:
            if score is not None:
                scores.append(score)
                quids.append(qid)
                if duration != -1:
                    durations.append(duration)
            else:
                failed_count += 1

        logger.info(
            f"Evaluation results for run {rid}: {len(scores)} successful, {failed_count} failed/missing"
        )

        if durations:
            avg_time = sum(durations) / len(durations)
            logger.info(f"Average time across evaluated tasks: {avg_time:.4f} s")
        else:
            avg_time = -1

        metrics = benchmark.compute_aggregate_metrics(scores, quids)
        logger.info(f"Evaluation metrics: {metrics}")

        # Add average time and scores to metrics
        metrics["average_time"] = avg_time
        metrics["scores"] = [
            (id, score.model_dump_json()) for id, score in zip(quids, scores)
        ]

        # Save metrics to a file
        metrics_path = os.path.join(output_dir, "metrics.json")
        with open(metrics_path, "w") as f:
            json.dump(metrics, f)
        logger.info(f"Metrics saved to {metrics_path}")

        all_scores.append(scores)
        all_durations.append(durations)
        all_quids.append(quids)
    if len(run_ids) > 1:
        benchmark = download_and_load_benchmark(
            benchmark_name, benchmark_dir, benchmark_constructor
        )
        aggregate_metrics = benchmark.compute_aggregate_metrics_multiple_runs(
            all_scores, all_durations, all_quids
        )

        # Save aggregate metrics to a file
        aggregate_metrics_path = os.path.join(
            runs_dir,
            "runs",
            system_name,
            benchmark_name,
            split or "all_benchmark",
            "aggregate_metrics.json",
        )
        with open(aggregate_metrics_path, "w") as f:
            json.dump(aggregate_metrics, f)
        logger.info(f"Aggregate metrics saved to {aggregate_metrics_path}")


def run_evaluate_benchmark_func(
    benchmark_name: str,
    system_name: str,
    parallel: int,
    benchmark_dir: str,
    runs_dir: str,
    split: Optional[str] = None,
    run_id: Union[int, List[int]] = 0,
    benchmark_constructor: Optional[Union[Callable[..., Benchmark], Benchmark]] = None,
    system_constructor: Optional[Union[Callable[..., BaseSystem], BaseSystem]] = None,
    subsample: Optional[float] = None,
    seed: Optional[int] = None,
    redo_eval: bool = False,
    reload_benchmark_per_task: bool = False,
    reload_system_per_task: bool = False,
    task_id: Optional[str] = None,
    base_task: Optional[str] = None,
    difficulty: Optional[str] = None,
    rerun_timedout: bool = False,
    verbose: bool = False,
) -> None:
    """Run benchmark evaluation and compute metrics.

    Args:
        benchmark_name (str): Name of the benchmark
        system_name (str): Name of the system to evaluate
        parallel (int): Number of parallel processes
        benchmark_dir (str): Directory containing benchmark data
        runs_dir (str): Directory to store outputs
        split (str, optional): Optional dataset split to evaluate
        run_id (int, List[int]): Run ID or list of run IDs. Default: 0
        benchmark_constructor (callable, optional): Optional callable to create benchmark instance
        system_constructor (callable | BaseSystem, optional): Optional callable or instance to create/use system
        subsample (float, optional): Optional fraction (0-1] of tasks to evaluate
        seed (int, optional): Optional random seed for reproducibility
        redo_eval (bool, optional): Whether to redo evaluation even if results exist. Default: False
        reload_benchmark_per_task (bool, optional): Whether to reload benchmark for each task. Default: False
        reload_system_per_task (bool, optional): Whether to reload system for each task. Default: False
    """
    if isinstance(run_id, int):
        run_ids = [run_id]
    else:
        run_ids = run_id

    for rid in run_ids:
        run_benchmark_func(
            benchmark_name=benchmark_name,
            system_name=system_name,
            parallel=parallel,
            benchmark_dir=benchmark_dir,
            runs_dir=runs_dir,
            split=split,
            run_id=rid,
            benchmark_constructor=benchmark_constructor,
            system_constructor=system_constructor,
            subsample=subsample,
            seed=seed,
            reload_benchmark_per_task=reload_benchmark_per_task,
            reload_system_per_task=reload_system_per_task,
            task_id=task_id,
            base_task=base_task,
            difficulty=difficulty,
            rerun_timedout=rerun_timedout,
            verbose=verbose,
        )
    evaluate_benchmark_func(
        benchmark_name=benchmark_name,
        system_name=system_name,
        benchmark_dir=benchmark_dir,
        runs_dir=runs_dir,
        split=split,
        run_id=run_ids,
        benchmark_constructor=benchmark_constructor,
        system_constructor=system_constructor,
        parallel=parallel,
        redo_eval=redo_eval,
        task_id=task_id,
        base_task=base_task,
        difficulty=difficulty,
        verbose=verbose,
    )
