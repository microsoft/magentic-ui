This benchmark focuses on testing AI agents' capabilities in persistent monitoring, state change detection, and task completion under varying complexity and noise levels.

## Quick Usage

To run SentinelBench evaluations:

```bash
python experiments/eval/run.py --current-dir . --dataset SentinelBench --split test --run-id 0 --parallel 1 --config experiments/endpoint_configs/config.yaml --mode run --web-surfer-only --run-without-docker --headless
```

**Note**: The above command uses the default SentinelBench URL (`https://sentinel-bench.vercel.app/`). See the "Local Hosting Setup" section below if you're hosting SentinelBench locally or at a different URL, and specify it with the flag `--sentinelbench-url http://YOUR_HOST_IP:5173/` when running the evaluation command above.

### Enable Sentinel Steps

You can append the `--enable-sentinel` flag to enable the usage SentinelSteps during planning:

```bash
python experiments/eval/run.py --current-dir . --dataset SentinelBench --split test --run-id 1 --parallel 1 --config experiments/endpoint_configs/config.yaml --mode run --web-surfer-only --run-without-docker --headless --enable-sentinel
```

### Enable Dynamic Sentinel Sleep

You can also enable dynamic sleep duration adjustment for sentinel steps with the `--enable-dynamic-sentinel-sleep` flag:

```bash
python experiments/eval/run.py --current-dir . --dataset SentinelBench --split test --run-id 1 --parallel 1 --config experiments/endpoint_configs/config.yaml --mode run --web-surfer-only --run-without-docker --headless --enable-sentinel --enable-dynamic-sentinel-sleep
```

This allows the LLM to dynamically adjust sleep durations based on the current state of the task, making sentinel steps more intelligent and responsive.

### Task Filtering

SentinelBench supports filtering tasks to run specific subsets:

**Run a specific task by ID:**
```bash
python experiments/eval/run.py --current-dir . --dataset SentinelBench --split test --run-id 1 --simulated-user-type none --parallel 1 --config experiments/endpoint_configs/config.yaml --mode run --task-id reactor-easy
```

**Run all variants of a specific task:**
```bash
python experiments/eval/run.py --current-dir . --dataset SentinelBench --split test --run-id 1 --simulated-user-type none --parallel 1 --config experiments/endpoint_configs/config.yaml --mode run --base-task reactor
```
This will run `reactor-easy`, `reactor-medium`, and `reactor-hard`.

**Filter by difficulty level:**
```bash
python experiments/eval/run.py --current-dir . --dataset SentinelBench --split test --run-id 1 --simulated-user-type none --parallel 1 --config experiments/endpoint_configs/config.yaml --mode run --difficulty easy
```

**Combine multiple filters:**
```bash
python experiments/eval/run.py --current-dir . --dataset SentinelBench --split test --run-id 1 --simulated-user-type none --parallel 1 --config experiments/endpoint_configs/config.yaml --mode run --base-task animal-mover --difficulty medium
```



### Local Hosting Setup

To host SentinelBench locally:

1. Clone the MagenticUI repository  
2. Navigate to the SentinelBench/ directory
3. Install dependencies and start the development server with: `npm run dev -- --host 0.0.0.0`
4. Note the IP address and port where the server is running (typically shown in the terminal output)
5. Use this URL with the `--sentinelbench-url` parameter

**Common local URLs:**
- Local development: `http://localhost:5173/` or `http://127.0.0.1:5173/`
- Network accessible: `http://YOUR_MACHINE_IP:5173/` (replace YOUR_MACHINE_IP with your actual IP)
- Docker/VM: Check your container/VM's IP address

## Running Analysis

By default, after completing all runs the script will automatically run `--mode eval` and score the performance of the system. If your run fails and you want to compile the successful runs, you can run the same command you did while replacing the `--mode run` with `--mode eval` as seen in the example below: 

```bash
python experiments/eval/run.py --current-dir . --dataset SentinelBench --split test --run-id 0 --parallel 1 --config experiments/endpoint_configs/config.yaml --mode eval --web-surfer-only --run-without-docker --headless
```

Once you have ran the evaluation mode for all your runs, you may choose to use the scripts within the `tools/` subdirectory to analyze results and create plots. This subdirectory has descriptions of how to use the tools.