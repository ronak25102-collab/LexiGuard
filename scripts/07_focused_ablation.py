"""Run the controlled local retrieval ablation and actual Ragas scoring."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lexiguard.evaluation.focused_ablation import main

if __name__ == "__main__":
    main()
