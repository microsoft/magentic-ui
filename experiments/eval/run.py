import json
import yaml
import os
import datetime
from typing import Optional, Dict, Any, Callable
import typer
from typing_extensions import Annotated
from magentic_ui.eval.core import run_evaluate_benchmark_func, evaluate_benchmark_func
from systems.magentic_ui_sim_user_system import MagenticUISimUserSystem
from systems.magentic_ui_system import MagenticUIAutonomousSystem
from magentic_ui.eval.systems import LLMSystem
from magentic_ui.eval.benchmarks import WebVoyagerBenchmark
from magentic_ui.eval.benchmark import Benchmark
from autogen_core.models import ChatCompletionClient
from magentic_ui.eval.benchmarks.sentinelbench.task_variants import SENTINELBENCH_TASK_VARIANTS, SENTINELBENCH_TEST_VARIANTS

# Create Typer app for evaluation CLI
app = typer.Typer(help="🧪 Magentic-UI Evaluation System", rich_markup_mode="rich")


def save_experiment_args(args: Dict[str, Any], system_name: str) -> None:
    """
    Save experiment arguments to a timestamped JSON file.

    Args:
        args (Dict[str, Any]): The arguments dictionary containing experiment parameters.
        system_name (str): The name of the system being evaluated.
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"args_{timestamp}.json"

    # Create the same directory structure as used in core.py
    save_dir = os.path.join(
        args["current_dir"],
        "runs",
        system_name,
        args["dataset"],
        args["split"] or "all_benchmark",
        str(args["run_id"]),
    )
    os.makedirs(save_dir, exist_ok=True)

    # Use args dict directly
    args_dict = args.copy()

    # Add only relevant client configurations if config file exists
    if args.get("config") and os.path.exists(args["config"]):
        config_contents = load_config(args["config"])
        if config_contents is not None:
            client_keys = [
                "orchestrator_client",
                "web_surfer_client",
                "coder_client",
                "file_surfer_client",
                "user_proxy_client",
            ]
            args_dict["client_configs"] = {
                k: config_contents.get(k) for k in client_keys if k in config_contents
            }
            args_dict["config_path"] = os.path.abspath(args["config"])

    filepath = os.path.join(save_dir, filename)
    with open(filepath, "w") as f:
        json.dump(args_dict, f, indent=4)

    print(f"Experiment args saved to {filepath}")


def load_config(config_path: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Load configuration from either YAML or JSON file.

    Args:
        config_path (Optional[str]): Path to the configuration file (YAML or JSON).

    Returns:
        Optional[Dict[str, Any]]: The loaded configuration as a dictionary, or None if not found.
    """
    if config_path is None:
        return None

    with open(config_path, "r") as f:
        if config_path.endswith((".yml", ".yaml")):
            config = yaml.safe_load(f)
            return config if config else None
        else:
            return json.load(f)


def run_system_evaluation(
    args: Dict[str, Any],
    system_constructor: Any,
    system_name: str,
    config: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Common function to run system evaluation to avoid code duplication.

    Args:
        args (Dict[str, Any]): The arguments dictionary containing experiment parameters.
        system_constructor (Any): The system instance or constructor to evaluate.
        system_name (str): The name of the system being evaluated.
        config (Optional[Dict[str, Any]]): Optional configuration dictionary.
    """
    benchmark_constructor: Optional[Callable[..., Benchmark]] = None
    if args["dataset"] == "WebVoyager":
        # Download the dataset (only needed once)
        client = ChatCompletionClient.load_component(
            {
                "provider": "OpenAIChatCompletionClient",
                    "config": {
                        "model": "gpt-5",
                },
                "max_retries": 10,
            }
        )
        # client = ChatCompletionClient.load_component(
        #     config['gpt4o_client']
        # )

        def create_benchmark(data_dir="WebVoyager", name="WebVoyager"):
            benchmark = WebVoyagerBenchmark(
                data_dir=data_dir,
                eval_method="gpt_eval",
                model_client=client,
            )
            return benchmark

        benchmark_constructor = create_benchmark
    elif args["dataset"] == "SentinelBench":
        # Import here to avoid circular import
        from magentic_ui.eval.benchmarks.sentinelbench.sentinelbench import SentinelBenchBenchmark
        
        def create_sentinelbench_benchmark(data_dir="SentinelBench", name="SentinelBench"):
            # Choose variants based on args or use defaults
            task_variants = None
            if args.get('use_test_variants'):
                task_variants = SENTINELBENCH_TEST_VARIANTS
            elif args.get('use_full_variants'):
                task_variants = SENTINELBENCH_TASK_VARIANTS
            
            benchmark = SentinelBenchBenchmark(
                data_dir=data_dir,
                name=name,
                task_variants=task_variants,
            )
            return benchmark
            
        benchmark_constructor = create_sentinelbench_benchmark
    elif args["dataset"] == "WebGames":
        # Keep original WebGames logic without variants
        benchmark_constructor = None
        # Load it into memory
    if args["mode"] == "eval":
        evaluate_benchmark_func(
            benchmark_name=args["dataset"],
            benchmark_constructor=benchmark_constructor,
            system_name=system_name,
            parallel=args["parallel"],
            benchmark_dir=args["current_dir"],
            runs_dir=args["current_dir"],
            split=args["split"],
            run_id=args["run_id"],
            system_constructor=system_constructor,
            redo_eval=args["redo_eval"],
            task_id=args["task_id"],
            base_task=args["base_task"],
            difficulty=args["difficulty"],
            verbose=args["verbose"],
        )
    else:
        run_evaluate_benchmark_func(
            benchmark_name=args["dataset"],
            benchmark_constructor=benchmark_constructor,
            system_name=system_name,
            parallel=args["parallel"],
            benchmark_dir=args["current_dir"],
            runs_dir=args["current_dir"],
            split=args["split"],
            run_id=args["run_id"],
            system_constructor=system_constructor,
            subsample=args["subsample"] if args["subsample"] < 1 else None,
            redo_eval=args["redo_eval"],
            task_id=args["task_id"],
            base_task=args["base_task"],
            difficulty=args["difficulty"],
            rerun_timedout=args["rerun_timedout"],
            verbose=args["verbose"],
        )


def run_system_sim_user(args: Dict[str, Any], system_name: str) -> None:
    """
    Run evaluation using the MagenticUISystem, which simulates user interactions.

    Args:
        args (Dict[str, Any]): The arguments dictionary containing experiment parameters.
        system_name (str): The name of the system being evaluated.
    """
    config = load_config(args["config"])

    if system_name == "LLM":
        # Use LLMSystem for LLM-based evaluations
        system = LLMSystem(
            system_name=system_name,
            endpoint_config=config.get("model_client") if config else None,
        )
    else:
        # system = MagenticUISimUserSystem(
        #     simulated_user_type=args.simulated_user_type,
        #     endpoint_config_orch=config.get("orchestrator_client") if config else None,
        #     endpoint_config_websurfer=config.get("web_surfer_client") if config else None,
        #     endpoint_config_coder=config.get("coder_client") if config else None,
        #     endpoint_config_file_surfer=config.get("file_surfer_client")
        #     if config
        #     else None,
        #     endpoint_config_user_proxy=config.get("user_proxy_client") if config else None,
        #     web_surfer_only=args.web_surfer_only,
        #     how_helpful_user_proxy=args.how_helpful_user_proxy,
        #     dataset_name=args.dataset,
        #     browser_headless=not args.browser_headful,
        # )
        system = MagenticUIAutonomousSystem(
            endpoint_config_orch=config.get("orchestrator_client") if config else None,
            endpoint_config_websurfer=config.get("web_surfer_client") if config else None,
            endpoint_config_coder=config.get("coder_client") if config else None,
            endpoint_config_file_surfer=config.get("file_surfer_client")
            if config
            else None,
            web_surfer_only=args["web_surfer_only"],
            dataset_name=args["dataset"],
            use_local_browser=args["use_local_browser"],
            sentinel_tasks=args["sentinel_tasks"],
            timeout_minutes=args["timeout_minutes"],
            verbose=args["verbose"],
            pretty_output=args["pretty_output"],
        )

    run_system_evaluation(args, system, system_name, config)


@app.command()
def main(
    # Core Configuration
    mode: Annotated[str, typer.Option(help="🎯 Mode to run", rich_help_panel="🏗️ Core Configuration")] = "run",
    current_dir: Annotated[str, typer.Option(help="📁 Current working directory", rich_help_panel="🏗️ Core Configuration")] = os.getcwd(),
    config: Annotated[Optional[str], typer.Option(help="⚙️ Path to endpoint configuration file for LLMs", rich_help_panel="🏗️ Core Configuration")] = None,
    
    # Dataset Configuration  
    dataset: Annotated[str, typer.Option(help="📊 Dataset name", rich_help_panel="📊 Dataset Configuration")] = "Gaia",
    split: Annotated[str, typer.Option(help="🔀 Dataset split to use", rich_help_panel="📊 Dataset Configuration")] = "validation-1",
    
    # Execution Configuration
    parallel: Annotated[int, typer.Option(help="🔄 Number of parallel processes to use", rich_help_panel="⚡ Execution Configuration")] = 1,
    run_id: Annotated[int, typer.Option(help="🆔 Run ID for the experiment", rich_help_panel="⚡ Execution Configuration")] = 1,
    subsample: Annotated[float, typer.Option(help="🎲 Subsample ratio for the dataset (only used in run mode)", rich_help_panel="⚡ Execution Configuration")] = 1.0,
    timeout_minutes: Annotated[int, typer.Option(help="⏱️ Timeout for each task in minutes", rich_help_panel="⚡ Execution Configuration")] = 15,
    
    # System Configuration
    system_type: Annotated[str, typer.Option(help="🤖 Type of system to run", rich_help_panel="🤖 System Configuration")] = "MagenticUI",
    web_surfer_only: Annotated[bool, typer.Option(help="🌐 Run only the web surfer agent", rich_help_panel="🤖 System Configuration")] = False,
    use_local_browser: Annotated[bool, typer.Option(help="🖥️ Run the browser locally, with a GUI (headful)", rich_help_panel="🤖 System Configuration")] = False,
    sentinel_tasks: Annotated[bool, typer.Option(help="🛡️ Enable sentinel tasks functionality in the orchestrator", rich_help_panel="🤖 System Configuration")] = False,
    
    # SentinelBench Options
    task_id: Annotated[Optional[str], typer.Option(help="🎯 Run a specific task by ID (e.g., 'reactor-easy') or multiple tasks separated by commas (e.g., 'reactor-easy,animal-mover-medium')", rich_help_panel="🛡️ SentinelBench Options")] = None,
    base_task: Annotated[Optional[str], typer.Option(help="📝 Run all variants of a specific task or multiple tasks separated by commas (e.g., 'reactor,animal-mover,linkedin-monitor')", rich_help_panel="🛡️ SentinelBench Options")] = None,  
    difficulty: Annotated[Optional[str], typer.Option(help="⚡ Filter tasks by difficulty level or multiple levels separated by commas (e.g., 'easy,medium')", rich_help_panel="🛡️ SentinelBench Options")] = None,
    use_test_variants: Annotated[bool, typer.Option(help="🧪 Use test variants for SentinelBench (smaller set)", rich_help_panel="🛡️ SentinelBench Options")] = False,
    use_full_variants: Annotated[bool, typer.Option(help="🎛️ Use full variants for SentinelBench (all combinations)", rich_help_panel="🛡️ SentinelBench Options")] = False,
    
    # Evaluation Options
    redo_eval: Annotated[bool, typer.Option(help="🔄 Redo evaluation even if results exist", rich_help_panel="📊 Evaluation Options")] = False,
    rerun_timedout: Annotated[bool, typer.Option(help="⏰ Rerun tasks that previously timed out", rich_help_panel="📊 Evaluation Options")] = False,
    
    # User Simulation (Legacy)
    simulated_user_type: Annotated[str, typer.Option(help="👤 Type of simulated user", rich_help_panel="👤 User Simulation (Legacy)")] = "none",
    how_helpful_user_proxy: Annotated[str, typer.Option(help="🤝 How helpful the user proxy should be", rich_help_panel="👤 User Simulation (Legacy)")] = "soft", 
    user_messages_data: Annotated[Optional[str], typer.Option(help="💬 Path to user messages data CSV file", rich_help_panel="👤 User Simulation (Legacy)")] = None,
    
    # Debugging
    verbose: Annotated[bool, typer.Option(help="🗣️ Enable verbose logging to show agent thinking", rich_help_panel="🛠️ Debugging")] = False,
    
    # Output Formatting
    pretty_output: Annotated[bool, typer.Option("--pretty-output/--no-pretty-output", help="🎨 Use pretty console formatting for agent output (default: disabled)", rich_help_panel="🎨 Output Formatting")] = False,
) -> None:
    """
    🧪 **Magentic-UI Evaluation System**
    Run or evaluate the Magentic-UI system on various benchmarks including SentinelBench, WebVoyager, and more.
    """
    # Convert to dictionary for compatibility with existing functions
    args = {
        "mode": mode,
        "current_dir": current_dir,
        "config": config,
        "dataset": dataset,
        "split": split,
        "parallel": parallel,
        "run_id": run_id,
        "subsample": subsample,
        "timeout_minutes": timeout_minutes,
        "system_type": system_type,
        "web_surfer_only": web_surfer_only,
        "use_local_browser": use_local_browser,
        "sentinel_tasks": sentinel_tasks,
        "task_id": task_id,
        "base_task": base_task,
        "difficulty": difficulty,
        "use_test_variants": use_test_variants,
        "use_full_variants": use_full_variants,
        "redo_eval": redo_eval,
        "rerun_timedout": rerun_timedout,
        "simulated_user_type": simulated_user_type,
        "how_helpful_user_proxy": how_helpful_user_proxy,
        "user_messages_data": user_messages_data,
        "verbose": verbose,
        "pretty_output": pretty_output,
    }
    
    # Validate mode
    if mode not in ["run", "eval"]:
        typer.echo("❌ Mode must be either 'run' or 'eval'", err=True)
        raise typer.Exit(1)
    
    # Validate system type
    if system_type not in ["MagenticUI", "magentic-ui-sim-user", "LLM"]:
        typer.echo("❌ System type must be one of: MagenticUI, magentic-ui-sim-user, LLM", err=True)
        raise typer.Exit(1)
    
    # Validate difficulty if specified
    if difficulty and difficulty not in ["easy", "medium", "hard"]:
        typer.echo("❌ Difficulty must be one of: easy, medium, hard", err=True)
        raise typer.Exit(1)

    # Determine system name based on arguments
    system_name = system_type
    if simulated_user_type != "none":
        system_name += f"_{simulated_user_type}_{how_helpful_user_proxy}"
    if web_surfer_only:
        system_name += "_web_surfer_only"

    # Display startup info
    if verbose:
        typer.echo("🔧 [bold green]VERBOSE MODE ENABLED[/bold green] - Agent conversations will be shown", color=True)
    
    typer.echo(f"🚀 Starting evaluation with system: [bold blue]{system_name}[/bold blue]", color=True)
    typer.echo(f"📊 Dataset: [yellow]{dataset}[/yellow], Mode: [cyan]{mode}[/cyan]", color=True)
    
    # Display task filtering info for SentinelBench
    if dataset == "SentinelBench":
        filter_info = []
        if task_id:
            task_count = len([t.strip() for t in task_id.split(",")])
            filter_info.append(f"Task IDs: [blue]{task_id}[/blue] ({task_count} task{'s' if task_count > 1 else ''})")
        if base_task:
            base_count = len([b.strip() for b in base_task.split(",")])
            filter_info.append(f"Base Tasks: [green]{base_task}[/green] ({base_count} task{'s' if base_count > 1 else ''})")
        if difficulty:
            diff_count = len([d.strip() for d in difficulty.split(",")])
            filter_info.append(f"Difficulties: [magenta]{difficulty}[/magenta] ({diff_count} level{'s' if diff_count > 1 else ''})")
        
        if filter_info:
            typer.echo("🔍 Task Filtering:", color=True)
            for info in filter_info:
                typer.echo(f"   • {info}", color=True)
    
    # Save experiment args
    save_experiment_args(args, system_name)

    # Run the appropriate system
    run_system_sim_user(args, system_name)


if __name__ == "__main__":
    app()
