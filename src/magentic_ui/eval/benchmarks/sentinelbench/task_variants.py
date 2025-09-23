"""
Configuration for SentinelBench task variants with different parameters.
"""

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
