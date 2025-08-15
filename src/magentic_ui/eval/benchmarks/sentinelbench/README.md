SentinelBench: A benchmark for evaluating AI agents on monitoring and long-term observation tasks.

This benchmark focuses on testing AI agents' capabilities in persistent monitoring, state change detection, and task completion under varying complexity and noise levels.

The benchmark includes 18 interactive web-based tasks designed around monitoring scenarios, from simple button pressing to complex social media monitoring.

## Task Characterization

Each task includes several dimensions for analysis:
- **difficulty**: easy, medium, hard
- **base_task**: underlying task type (e.g., reactor, animal-mover, button-presser)
- **duration**: Short, Medium, Long
- **criteria**: Objective, Subjective, Mixed
- **activity**: Active (requires user interaction), Passive (monitoring/waiting)
- **noise**: Clean, Noisy, Very Noisy
- **realism**: Playful, Realistic

## Usage

To run SentinelBench evaluations:

```bash
python experiments/eval/run.py --current-dir . --dataset SentinelBench --split test --run-id 1 --simulated-user-type none --parallel 1 --config experiments/endpoint_configs/config.yaml --mode run
```

## Local Hosting

SentinelBench is designed to be hosted locally during development and testing. The default configuration expects the benchmark website to be running at `http://localhost:5174/`.

To host SentinelBench locally:
1. Clone the SentinelBench repository
2. Install dependencies and start the development server
3. Ensure it's accessible at the expected URL
