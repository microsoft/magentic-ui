"""
Configuration for SentinelBench task variants with different parameters and timeout settings.
"""

from typing import Dict, List, Any, cast

# Define task variants with different parameter values for SentinelBench
SENTINELBENCH_TASK_VARIANTS = {
    # Time-based variants
    # Reactor variants
    "reactor-easy": [30, 60, 300, 900, 3600, 7200, 14400, 28800, 57600],
    "reactor-medium": [30, 60, 300, 900, 3600, 7200, 14400, 28800, 57600],
    "reactor-hard": [30, 60, 300, 900, 3600, 7200, 14400, 28800, 57600],
    # Teams monitor variants
    "teams-monitor-easy": [30, 60, 300, 900, 3600, 7200],
    "teams-monitor-medium": [30, 60, 300, 900, 3600, 7200],
    "teams-monitor-hard": [30, 60, 300, 900, 3600, 7200],
    # LinkedIn monitor variants
    "linkedin-monitor-easy": [30, 60, 300, 900, 3600, 7200],
    "linkedin-monitor-medium": [30, 60, 300, 900, 3600, 7200],
    "linkedin-monitor-hard": [30, 60, 300, 900, 3600, 7200],
    # Flight booker variants
    "flight-monitor-easy": [30, 60, 300, 900, 3600, 7200],
    "flight-monitor-medium": [30, 60, 300, 900, 3600, 7200],
    "flight-monitor-hard": [30, 60, 300, 900, 3600, 7200],
    # News checker variants
    "news-checker-easy": [30, 60, 300, 900, 3600, 7200],
    "news-checker-medium": [30, 60, 300, 900, 3600, 7200],
    "news-checker-hard": [30, 60, 300, 900, 3600, 7200],
    # GitHub watcher variants
    "github-watcher-easy": [30, 60, 300, 900, 3600, 7200],
    "github-watcher-medium": [30, 60, 300, 900, 3600, 7200],
    "github-watcher-hard": [30, 60, 300, 900, 3600, 7200],
    # Count-based variants
    # Animal mover variants
    "animal-mover-easy": [2, 4, 8, 16, 32, 64],
    "animal-mover-medium": [2, 4, 8, 16, 32, 64],
    "animal-mover-hard": [2, 4, 8, 16, 32, 64],
    # Button presser variants
    "button-presser-easy": [2, 4, 8, 16, 32, 64],
    "button-presser-medium": [2, 4, 8, 16, 32, 64],
    "button-presser-hard": [2, 4, 8, 16, 32, 64],
}

# Quick test variants (smaller set for testing)
SENTINELBENCH_TEST_VARIANTS = {
    # Time-based test variants (2 time points) - all tasks have easy/medium/hard variants
    # Reactor variants
    "reactor-easy": [30],
    "reactor-medium": [30],
    "reactor-hard": [30],
    # Teams monitor variants
    "teams-monitor-easy": [30],
    "teams-monitor-medium": [30],
    "teams-monitor-hard": [30],
    # LinkedIn monitor variants
    "linkedin-monitor-easy": [30],
    "linkedin-monitor-medium": [30],
    "linkedin-monitor-hard": [30],
    # Flight booker variants
    "flight-monitor-easy": [30],
    "flight-monitor-medium": [30],
    "flight-monitor-hard": [30],
    # News checker variants
    "news-checker-easy": [30],
    "news-checker-medium": [30],
    "news-checker-hard": [30],
    # GitHub watcher variants
    "github-watcher-easy": [30],
    "github-watcher-medium": [30],
    "github-watcher-hard": [30],
    # Count-based test variants (2 count points) - all tasks have easy/medium/hard variants
    # Animal mover variants
    "animal-mover-easy": [2],
    "animal-mover-medium": [2],
    "animal-mover-hard": [2],
    # Button presser variants (same scaling as animal-mover)
    "button-presser-easy": [2],
    "button-presser-medium": [2],
    "button-presser-hard": [2],
}

# Timeout configuration for SentinelBench tasks
DURATION_TASK_TIMEOUTS = {
    30: 30,  # 30s task -> 30min timeout
    60: 30,  # 60s task -> 30min timeout
    300: 45,  # 5min task -> 45min timeout
    900: 60,  # 15min task -> 60min timeout
    3600: 90,  # 1h task -> 90min timeout
    7200: 180,  # 2h task -> 180min timeout
}

COUNT_TASK_TIMEOUTS = {
    2: 10,  # 2 actions -> 10min timeout
    4: 15,  # 4 actions -> 15min timeout
    8: 30,  # 8 actions -> 30min timeout
    16: 60,  # 16 actions -> 60min timeout
    32: 90,  # 32 actions -> 90min timeout
    64: 120,  # 64 actions -> 120min timeout
}

# Task categorization sets
DURATION_TASKS = {
    "reactor-easy",
    "reactor-medium",
    "reactor-hard",
    "teams-monitor-easy",
    "teams-monitor-medium",
    "teams-monitor-hard",
    "linkedin-monitor-easy",
    "linkedin-monitor-medium",
    "linkedin-monitor-hard",
    "flight-monitor-easy",
    "flight-monitor-medium",
    "flight-monitor-hard",
    "news-checker-easy",
    "news-checker-medium",
    "news-checker-hard",
    "github-watcher-easy",
    "github-watcher-medium",
    "github-watcher-hard",
}

COUNT_TASKS = {
    "animal-mover-easy",
    "animal-mover-medium",
    "animal-mover-hard",
    "button-presser-easy",
    "button-presser-medium",
    "button-presser-hard",
}

# Default parameter values for known parameterizable tasks
# All tasks will have easy/medium/hard variants in the final dataset
SENTINELBENCH_DEFAULT_PARAMS = {
    # Time-based tasks (duration in seconds) - all variants
    "reactor-easy": {"duration": 30},
    "reactor-medium": {"duration": 30},
    "reactor-hard": {"duration": 30},
    "teams-monitor-easy": {"duration": 30},
    "teams-monitor-medium": {"duration": 30},
    "teams-monitor-hard": {"duration": 30},
    "linkedin-monitor-easy": {"duration": 30},
    "linkedin-monitor-medium": {"duration": 30},
    "linkedin-monitor-hard": {"duration": 30},
    "flight-monitor-easy": {"duration": 30},
    "flight-monitor-medium": {"duration": 30},
    "flight-monitor-hard": {"duration": 30},
    "news-checker-easy": {"duration": 30},
    "news-checker-medium": {"duration": 30},
    "news-checker-hard": {"duration": 30},
    "github-watcher-easy": {"duration": 30},
    "github-watcher-medium": {"duration": 30},
    "github-watcher-hard": {"duration": 30},
    # Count-based tasks (number of items/actions) - all variants
    # Both use same scaling: [2, 4, 8, 16, 32, 64]
    "animal-mover-easy": {"count": 2},
    "animal-mover-medium": {"count": 2},
    "animal-mover-hard": {"count": 2},
    "button-presser-easy": {"count": 2},
    "button-presser-medium": {"count": 2},
    "button-presser-hard": {"count": 2},
}

# Model pricing for cost calculations ($/1K tokens)
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    # OpenAI GPT
    "gpt-4o": {"input": 0.005, "output": 0.02},  # Standard
    "gpt-4o-batch": {"input": 0.0025, "output": 0.01},  # Batch/Azure
    "gpt-4o-2024-08-06": {"input": 0.005, "output": 0.02},
    "gpt-4o-2024-11-20": {"input": 0.005, "output": 0.02},
    "gpt-4o-mini": {
        "input": 0.0006,
        "output": 0.0024,
    },  # Standard (Batch = 0.0003/0.0012)
    "gpt-4o-mini-2024-07-18": {"input": 0.0006, "output": 0.0024},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "gpt-5-mini": {
        "input": 0.00025,
        "output": 0.002,
    },  # GPT-5 mini: $0.25/$2.00 per 1M tokens
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

# Task type patterns for categorization
DURATION_TASK_PATTERNS: List[str] = [
    "reactor",
    "linkedin-monitor",
    "news-checker",
    "teams-monitor",
    "flight-monitor",
    "github-watcher",
]
COUNT_TASK_PATTERNS: List[str] = ["animal-mover", "button-presser"]

# Expected dimensions mapping (used by comparison tools)
EXPECTED_DIMENSIONS: Dict[str, List[int]] = {
    # Time-based variants
    "reactor-easy": [30, 60, 300, 900, 3600, 7200],
    "reactor-medium": [30, 60, 300, 900, 3600, 7200],
    "reactor-hard": [30, 60, 300, 900, 3600, 7200],
    "teams-monitor-easy": [30, 60, 300, 900, 3600, 7200],
    "teams-monitor-medium": [30, 60, 300, 900, 3600, 7200],
    "teams-monitor-hard": [30, 60, 300, 900, 3600, 7200],
    "linkedin-monitor-easy": [30, 60, 300, 900, 3600],
    "linkedin-monitor-medium": [30, 60, 300, 900, 3600],
    "linkedin-monitor-hard": [30, 60, 300, 900, 3600],
    "flight-monitor-easy": [30, 60, 300, 900, 3600, 7200],
    "flight-monitor-medium": [30, 60, 300, 900, 3600, 7200],
    "flight-monitor-hard": [30, 60, 300, 900, 3600, 7200],
    "news-checker-easy": [30, 60, 300, 900, 3600, 7200],
    "news-checker-medium": [30, 60, 300, 900, 3600, 7200],
    "news-checker-hard": [30, 60, 300, 900, 3600, 7200],
    "github-watcher-easy": [30, 60, 300, 900, 3600, 7200],
    "github-watcher-medium": [30, 60, 300, 900, 3600, 7200],
    "github-watcher-hard": [30, 60, 300, 900, 3600, 7200],
    # Count-based variants
    "animal-mover-easy": [2, 4, 8, 16, 32, 64],
    "animal-mover-medium": [2, 4, 8, 16, 32, 64],
    "animal-mover-hard": [2, 4, 8, 16, 32, 64],
    "button-presser-easy": [2, 4, 8, 16, 32, 64],
    "button-presser-medium": [2, 4, 8, 16, 32, 64],
    "button-presser-hard": [2, 4, 8, 16, 32, 64],
}


def calculate_sentinelbench_timeout(
    task: Any, default_timeout_minutes: int = 15
) -> int:
    """
    Calculate timeout in seconds for SentinelBench tasks based on parameter values.

    Args:
        task: The task object containing metadata with parameter_value
        default_timeout_minutes: Default timeout in minutes if no specific mapping found

    Returns:
        int: Timeout in seconds
    """
    # Default timeout in seconds
    default_timeout = 60 * default_timeout_minutes

    # Check if this is a SentinelBench task with parameter_value
    if hasattr(task, "metadata") and task.metadata and isinstance(task.metadata, dict):
        task_metadata: Any = getattr(task, "metadata", {})
        metadata: Dict[str, Any] = cast(Dict[str, Any], task_metadata)
        if "parameter_value" in metadata:
            parameter_value: Any = metadata["parameter_value"]

            # Get base task ID (remove parameter part if present)
            base_task_id = (
                task.id.split("/")[0] if hasattr(task, "id") and task.id else ""
            )

            # Duration-based tasks
            if base_task_id in DURATION_TASKS:
                timeout_minutes = DURATION_TASK_TIMEOUTS.get(
                    parameter_value, default_timeout_minutes
                )
                return timeout_minutes * 60

            # Count-based tasks
            elif base_task_id in COUNT_TASKS:
                timeout_minutes = COUNT_TASK_TIMEOUTS.get(
                    parameter_value, default_timeout_minutes
                )
                return timeout_minutes * 60

    return default_timeout


def get_timeout_display_info(task: Any, timeout_seconds: int) -> str:
    """
    Get formatted timeout display string for SentinelBench tasks.

    Args:
        task: The task object containing metadata
        timeout_seconds: Calculated timeout in seconds

    Returns:
        str: Formatted display string
    """
    timeout_minutes = int(timeout_seconds / 60)

    # Check if this is a SentinelBench task with parameter_value
    if hasattr(task, "metadata") and task.metadata and isinstance(task.metadata, dict):
        task_metadata: Any = getattr(task, "metadata", {})
        metadata: Dict[str, Any] = cast(Dict[str, Any], task_metadata)
        if "parameter_value" in metadata:
            parameter_value: Any = metadata["parameter_value"]
            base_task_id = (
                task.id.split("/")[0] if hasattr(task, "id") and task.id else ""
            )

            # Duration-based tasks
            if base_task_id in DURATION_TASKS:
                # Format duration display properly
                if parameter_value < 60:
                    duration_display = f"{parameter_value}s"
                elif parameter_value < 3600:
                    duration_display = f"{int(parameter_value/60)}min"
                else:
                    duration_display = f"{int(parameter_value/3600)}h"

                return f"{timeout_minutes}min for {duration_display} task"

            # Count-based tasks
            elif base_task_id in COUNT_TASKS:
                return f"{timeout_minutes}min for {parameter_value} actions"

    return f"{timeout_minutes}min (default)"
