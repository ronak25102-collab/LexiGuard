import logging
from collections.abc import Callable
from typing import Any

from datasets import Dataset, load_dataset

logger = logging.getLogger(__name__)

def load_cuad_test_set(num_questions: int = 20) -> list[dict[str, Any]]:
    """
    Load the CUAD QA dataset and sample questions.
    """
    logger.info(f"Loading {num_questions} questions from CUAD QA dataset...")
    try:
        dataset = load_dataset("theatticusproject/cuad-qa", split="test")

        selected = []
        for item in dataset:
            if not item["answers"]["text"]:
                continue

            selected.append({
                "question": item["question"],
                "ground_truth": item["answers"]["text"][0],
                "contract_name": item["title"],
                "clause_type": item["id"].split("__")[0] if "__" in item["id"] else "unknown"
            })

            if len(selected) >= num_questions:
                break

        logger.info(f"Successfully loaded {len(selected)} questions.")
        return selected
    except Exception as e:
        logger.error(f"Failed to load CUAD dataset: {e}")
        return []

def build_evaluation_dataset(test_questions: list[dict[str, Any]], run_agent_fn: Callable) -> Dataset:
    """
    Run questions through the agent and build a HuggingFace Dataset for Ragas.
    """
    logger.info(f"Building evaluation dataset with {len(test_questions)} questions...")

    eval_data = {
        "question": [],
        "answer": [],
        "contexts": [],
        "ground_truth": []
    }

    for i, item in enumerate(test_questions):
        logger.info(f"Processing question {i+1}/{len(test_questions)}")
        try:
            # Run the agent
            result = run_agent_fn(item["question"], None)

            answer = result.get("answer", "")

            # Extract context strings
            contexts = []
            for src in result.get("sources", []):
                if isinstance(src, dict):
                    contexts.append(src.get("clause_text", str(src)))
                else:
                    contexts.append(str(src))

            eval_data["question"].append(item["question"])
            eval_data["answer"].append(answer)
            eval_data["contexts"].append(contexts)
            eval_data["ground_truth"].append(item["ground_truth"])

        except Exception as e:
            logger.error(f"Error processing question: {item['question']}. Error: {e}")

    return Dataset.from_dict(eval_data)
