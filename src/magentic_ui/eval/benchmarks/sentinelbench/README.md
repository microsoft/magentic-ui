This benchmark focuses on testing AI agents' capabilities in persistent monitoring, state change detection, and task completion under varying complexity and noise levels.

## Usage

To run SentinelBench evaluations:

```bash
python experiments/eval/run.py --current-dir . --dataset SentinelBench --split test --run-id 1 --simulated-user-type none --parallel 1 --config experiments/endpoint_configs/config.yaml --mode run
```

**Note**: The above command uses the default SentinelBench URL (`https://sentinel-bench.vercel.app/`). If you're hosting SentinelBench locally or at a different URL, specify it with `--sentinelbench-url`:

```bash
python experiments/eval/run.py --current-dir . --dataset SentinelBench --split test --run-id 1 --simulated-user-type none --parallel 1 --config experiments/endpoint_configs/config.yaml --mode run --sentinelbench-url http://YOUR_HOST_IP:5173/
```

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

*For all examples above, add `--sentinelbench-url http://YOUR_HOST_IP:5173/` if using a custom URL instead of the default.*

## URL Configuration

SentinelBench evaluations use `https://sentinel-bench.vercel.app/` by default. For local development or custom deployments, you can override this URL.

### Using Default (Production) URL
No additional configuration needed - just run the commands as shown above.

### Using Custom/Local URL
Add `--sentinelbench-url` parameter to specify your custom URL:

```bash
python experiments/eval/run.py --dataset SentinelBench --sentinelbench-url http://localhost:5173/ [other options]
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

We provide all scripts to run analysis within the tools/ subdirectory. This subdirectory also contains a README.md file with explanations of the order the tools should be ran and how to better utilize them.