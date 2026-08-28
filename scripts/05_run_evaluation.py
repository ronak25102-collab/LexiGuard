#!/usr/bin/env python3
"""Script 05: Run Ragas evaluation on the LexiGuard pipeline."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lexiguard.evaluation.evaluate import run_full_evaluation


def main():
    print("=" * 60)
    print("LexiGuard - Step 5: Ragas Evaluation")
    print("=" * 60)

    results = run_full_evaluation(num_questions=20)

    print("\n" + "=" * 60)
    print("Evaluation complete! Results saved to evaluation_results/")
    print("=" * 60)


if __name__ == "__main__":
    main()
