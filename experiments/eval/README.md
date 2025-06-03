# Reproducing Experimental Results

Make sure to clone the repo and install Magentic-UI. From the root of the repo you can run these commands to reproduce our experimental results.

To evaluate an existing run or get partial results, replace "--mode run" with "--mode eval". See [experiments/eval/run.py](experiments/eval/run.py) for more information about the arguments.

The run.py script takes care of running Magentic-UI on the benchmark of choice. It will download the data in `./data` folder at the root of the repo and store the run logs inside `runs/[SYSTEM NAME]/[DATASET NAME]/[SPLIT NAME]/[RUN ID]`. Inside this folder you'll find a folder for each task with files containing the run messages (`[TASK_ID]_messages.json`), time data (`times.json`), token usage data (`model_tokens_usage.json`), evaluation scores (`score.json`) and any screenshots (`screenshot_raw_[TIMESTAMP].png` and `screenshot*som*[TIMESTAMP].png`) or produced files. You will also find a `metrics.json` file with metrics for the entire run.


**NOTE:** Make sure to create a config file with your model client endpoints. We provide a template config file [config_template.yaml](../endpoint_configs/config_template.yaml) that you should adapt. You should copy and rename this file to `config.yaml` inside `experiments/endpoint_configs` directory.

## WebGames

```bash
python experiments/eval/run.py --current-dir . --dataset WebGames --split test  --run-id 1 --simulated-user-type none --parallel 1 --config experiments/endpoint_configs/config.yaml --mode run
```

## WebVoyager

```bash
python experiments/eval/run.py  --current-dir . --dataset WebVoyager --split webvoyager  --run-id 1 --simulated-user-type none --parallel 1 --config experiments/endpoint_configs/config.yaml --web-surfer-only true --mode run
```

## GAIA

### Simulated User

On the validation set we first get autonomous performance:

```bash
python experiments/eval/run.py  --current-dir . --dataset Gaia --split validation   --run-id 1 --simulated-user-type none --parallel 1 --config experiments/endpoint_configs/config.yaml  --mode run
```

Then the simulated user with a stronger model (make sure your config file is correct first).

```bash
python experiments/eval/run.py  --current-dir . --dataset Gaia --split validation --run-id 2 --simulated-user-type co-planning-and-execution --how-helpful-user-proxy no_hints --parallel 1 --config experiments/endpoint_configs/config.yaml  --mode run
```

Then the simulated user with access to metadata.

```bash
python experiments/eval/run.py  --current-dir . --dataset Gaia --split validation --run-id 3 --simulated-user-type co-planning-and-execution --how-helpful-user-proxy soft --parallel 1 --config experiments/endpoint_configs/config.yaml  --mode run
```

To explore the results of these runs, you can use the following scripts that generate a CSV inside the logs directory:

```bash
python experiments/eval/explore_results.py --run-dir runs/MagenticUI_co-planning-and-execution_soft/Gaia/validation/3 --data-dir data/Gaia
```

and

```bash
python experiments/eval/analyze_sim_user.py --run-dir runs/MagenticUI_co-planning-and-execution_soft/Gaia/validation/3
```

### Test Set

```bash
python experiments/eval/run.py  --current-dir . --dataset Gaia --split test   --run-id 1 --simulated-user-type none --parallel 1 --config experiments/endpoint_configs/config.yaml  --mode run
```

You can use the [experiments/eval/prepare_for_submission.py](experiments/eval/prepare_for_submission.py) script to submit to the Gaia and AssistantBench leaderboard.

## AssistantBench

```bash
 python experiments/eval/run.py  --current-dir . --dataset AssistantBench --split test   --run-id 1 --simulated-user-type none --parallel 1 --config experiments/endpoint_configs/config.yaml  --mode run
```