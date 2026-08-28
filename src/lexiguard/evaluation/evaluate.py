import logging
from pathlib import Path

import sys
from unittest.mock import MagicMock

# PATCH: Ragas 0.2 hard-depends on langchain_community.chat_models.vertexai
# which was removed in langchain-community 0.3.0+. We mock it to allow imports.
if 'langchain_community.chat_models.vertexai' not in sys.modules:
    mock_vertex = MagicMock()
    mock_vertex.ChatVertexAI = MagicMock
    sys.modules['langchain_community.chat_models.vertexai'] = mock_vertex

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
        return result
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        return None

def generate_report(result, output_path: Path = None, json_path: Path = None) -> str:
    """Generate a markdown report and JSON data from the evaluation results."""
    if not result:
        return ""
        
    logger.info("Generating evaluation report...")
    
    # Get aggregate scores
    agg_scores = dict(result)

    report = "# LexiGuard Evaluation Report\n\n"
    report += "## Aggregate Scores\n\n"
    report += "| Metric | Score |\n"
    report += "|--------|-------|\n"

    for metric_name, score in agg_scores.items():
        report += f"| {metric_name} | {score:.4f} |\n"

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        logger.info(f"Report saved to {output_path}")

    # Generate JSON for frontend
    if json_path:
        import json
        df = result.to_pandas()
        
        # Prepare data for frontend
        frontend_data = []
        for i, row in df.iterrows():
            question = str(row.get('user_input', f'Q{i+1}'))
            
            # Shorten question for chart label if it's too long
            short_q = question[:15] + "..." if len(question) > 15 else question
            
            frontend_data.append({
                "question": f"Q{i+1} ({short_q})",
                "full_question": question,
                "faithfulness": float(row.get('faithfulness', 0)),
                "context_precision": float(row.get('llm_context_precision_with_reference', 0)),
                "answer_relevancy": float(row.get('answer_relevancy', 0)) # Included if we add the metric later
            })
            
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(frontend_data, f, indent=2)
        logger.info(f"JSON data saved to {json_path}")

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

    # 4. Generate report and JSON
    if results:
        report_path = Path("evaluation_results.md")
        json_path = Path("evaluation_results.json")
        generate_report(results, report_path, json_path)

    logger.info("Evaluation complete.")
    return dict(results) if results else {}

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_full_evaluation(num_questions=5)  # Use 5 for a quick test run
