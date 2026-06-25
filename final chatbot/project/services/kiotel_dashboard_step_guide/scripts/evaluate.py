import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from configs.logging_config import get_logger
from src.evaluation.ragas_eval import RAGEvaluator, DEFAULT_TEST_DATASET

logger = get_logger("evaluate")


def run():
    test_data_path = Path("./data/eval_dataset.json")
    if test_data_path.exists():
        with open(test_data_path) as f:
            dataset = json.load(f)
        logger.info("loaded_custom_dataset", samples=len(dataset))
    else:
        dataset = DEFAULT_TEST_DATASET
        logger.info("using_default_dataset", samples=len(dataset))

    evaluator = RAGEvaluator()
    report = evaluator.run(dataset)

    print("\n=== RAGAS Evaluation Results ===")
    if not report["scores"]:
        print("  No scores produced — check logs for errors.")
    else:
        for metric, score in report["scores"].items():
            try:
                print(f"  {metric}: {float(score):.4f}")
            except (TypeError, ValueError):
                print(f"  {metric}: {score}")
    print(f"\nFull report saved to ./evaluation_results/")


if __name__ == "__main__":
    run()