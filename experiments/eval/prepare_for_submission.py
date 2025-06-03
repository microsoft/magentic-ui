import os
import json
import argparse
from typing import Dict, Any, List


def load_questions_gaia(metadata_path: str) -> Dict[str, str]:
    """Load questions from a Gaia metadata JSONL file."""
    questions: Dict[str, str] = {}
    with open(metadata_path, "r") as f:
        for line in f:
            entry = json.loads(line)
            questions[entry["task_id"]] = entry["Question"]
    return questions


def load_questions_assistantbench(metadata_path: str) -> Dict[str, str]:
    """Load questions from an AssistantBench metadata JSONL file."""
    questions: Dict[str, str] = {}
    with open(metadata_path, "r") as f:
        for line in f:
            entry = json.loads(line)
            questions[entry["id"]] = entry["task"]
    return questions


def prepare_for_submission_gaia(base_dir: str, metadata_path: str) -> None:
    """Prepare Gaia model answers for submission by aggregating answers and questions into a JSONL file."""
    questions = load_questions_gaia(metadata_path)
    task_ids = [
        d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))
    ]
    results: List[Dict[str, Any]] = []
    found_task_ids = set()
    for task_id in task_ids:
        answer_path = os.path.join(base_dir, task_id, f"{task_id}_answer.json")
        if os.path.exists(answer_path):
            with open(answer_path, "r") as f:
                data = json.load(f)
            answer = data.get("answer", "")
            if answer == "Unable to determine":
                answer = ""
            question = questions.get(task_id, "")
            results.append(
                {
                    "task_id": task_id,
                    "question": question,
                    "model_answer": answer,
                    "reasoning_trace": "Reasoning trace not available",
                }
            )
            found_task_ids.add(task_id)
    # Add missing questions from metadata
    for task_id, question in questions.items():
        if task_id not in found_task_ids:
            results.append(
                {
                    "task_id": task_id,
                    "question": question,
                    "answer": "",
                    "reasoning_trace": "Reasoning trace not available",
                }
            )
    # Write to model_answers.jsonl in base_dir
    output_file = os.path.join(base_dir, "model_answers.jsonl")
    with open(output_file, "w") as f:
        for item in results:
            f.write(json.dumps(item) + "\n")


def prepare_for_submission_assistantbench(base_dir: str, metadata_path: str) -> None:
    """Prepare AssistantBench model answers for submission by aggregating answers and questions into a JSONL file."""
    questions = load_questions_assistantbench(metadata_path)
    task_ids = [
        d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))
    ]
    results: List[Dict[str, Any]] = []
    found_ids = set()
    for task_id in task_ids:
        answer_path = os.path.join(base_dir, task_id, f"{task_id}_answer.json")
        if os.path.exists(answer_path):
            with open(answer_path, "r") as f:
                data = json.load(f)
            # Expecting {"id": ..., "answer": ...}
            id_ = data.get("id", task_id)
            model_answer = data.get("answer", "")
            if model_answer in ("Unable to determine", "None"):
                model_answer = ""
            # question = questions.get(id_, "")
            results.append(
                {
                    "id": id_,
                    # "question": question,
                    "answer": model_answer,
                }
            )
            found_ids.add(id_)
    # Add missing questions from metadata
    for id_, question in questions.items():
        if id_ not in found_ids:
            results.append(
                {
                    "id": id_,
                    # "question": question,
                    "answer": "",
                }
            )
    # Write to model_answers.jsonl in base_dir
    output_file = os.path.join(base_dir, "model_answers.jsonl")
    with open(output_file, "w") as f:
        for item in results:
            f.write(json.dumps(item) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Prepare model answers for submission."
    )
    parser.add_argument("base_dir", help="Base directory containing task folders.")
    parser.add_argument("--metadata", default="", help="Path to metadata.jsonl file.")
    parser.add_argument("--dataset", default="Gaia", help="Dataset name.")
    args = parser.parse_args()
    if args.dataset == "Gaia":
        prepare_for_submission_gaia(args.base_dir, args.metadata)
    elif args.dataset == "AssistantBench":
        prepare_for_submission_assistantbench(args.base_dir, args.metadata)
    else:
        raise ValueError(f"Dataset {args.dataset} not supported.")
