import logging
from pathlib import Path

from datasets import Dataset
from ragas import evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import Faithfulness, LLMContextPrecisionWithReference

from lexiguard.agent.graph import run_agent
from lexiguard.agent.nodes import get_llm
from lexiguard.evaluation.test_set import build_evaluation_dataset, load_cuad_test_set

logger = logging.getLogger(__name__)

def run_evaluation(dataset: Dataset) -> dict:
    """Run Ragas evaluation on the dataset."""
    logger.info("Initializing Ragas evaluation...")

    # Initialize the LLM wrapper for Ragas using the configured provider
    llm = get_llm()
    evaluator_llm = LangchainLLMWrapper(llm)

    # Initialize metrics
    metrics = [
        Faithfulness(llm=evaluator_llm),
        LLMContextPrecisionWithReference(llm=evaluator_llm)
    ]

    logger.info("Running evaluation...")
    try:
        # Run evaluation using ragas 0.2+ API
        result = evaluate(
            dataset=dataset,
            metrics=metrics
        )
        return dict(result)
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        return {}

def generate_report(results: dict, output_path: Path = None) -> str:
    """Generate a markdown report from the evaluation results."""
    logger.info("Generating evaluation report...")

    report = "# LexiGuard Evaluation Report\n\n"
    report += "## Aggregate Scores\n\n"
    report += "| Metric | Score |\n"
    report += "|--------|-------|\n"

    for metric_name, score in results.items():
        report += f"| {metric_name} | {score:.4f} |\n"

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        logger.info(f"Report saved to {output_path}")

    return report

def run_full_evaluation(num_questions: int = 20) -> dict:
    """Run the complete evaluation pipeline."""
    logger.info(f"Starting full evaluation with {num_questions} questions.")

    # 1. Load test set
    test_questions = load_cuad_test_set(num_questions=num_questions)
    if not test_questions:
        logger.error("Failed to load test questions. Aborting.")
        return {}

    # 2. Build dataset
    dataset = build_evaluation_dataset(test_questions, run_agent)

    # 3. Evaluate
    results = run_evaluation(dataset)

    # 4. Generate report
    if results:
        report_path = Path("evaluation_results.md")
        generate_report(results, report_path)

    logger.info("Evaluation complete.")
    return results

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_full_evaluation(num_questions=5)  # Use 5 for a quick test run
