import json
from pathlib import Path
from typing import List
from datetime import datetime

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_openai import ChatOpenAI
from langchain_community.embeddings import HuggingFaceEmbeddings

from configs.settings import get_settings
from configs.logging_config import get_logger
from src.generation.rag_chain import RAGChain

logger = get_logger(__name__)


def _build_ragas_llm():
    settings = get_settings()
    return LangchainLLMWrapper(
        ChatOpenAI(
            model=settings.ragas_llm_model,
            openai_api_key=settings.ragas_llm_api_key,
            openai_api_base=settings.ragas_llm_base_url,
            temperature=0,
            request_timeout=120,
            max_retries=3,
        )
    )


def _build_ragas_embeddings():
    settings = get_settings()
    return LangchainEmbeddingsWrapper(
        HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
            model_kwargs={"device": settings.embedding_device},
            encode_kwargs={"normalize_embeddings": True},
        )
    )


class RAGEvaluator:
    def __init__(self, output_dir: str = "./evaluation_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.chain = RAGChain()

    def run(self, test_dataset: List[dict]) -> dict:
        questions, answers, contexts, ground_truths = [], [], [], []

        for sample in test_dataset:
            question = sample["question"]
            ground_truth = sample.get("ground_truth", "")
            try:
                response = self.chain.query(question)
                answer = response.answer if not response.blocked else ""
                ctx = [d["content"] for d in response.source_documents[:5]]
            except Exception as e:
                logger.error("sample_query_failed", question=question[:60], error=str(e))
                answer = ""
                ctx = []

            questions.append(question)
            answers.append(answer)
            contexts.append(ctx)
            ground_truths.append(ground_truth)
            logger.info("evaluated_sample", question=question[:60])

        dataset = Dataset.from_dict({
            "question": questions,
            "answer": answers,
            "contexts": contexts,
            "reference": ground_truths,
        })

        ragas_llm = _build_ragas_llm()
        ragas_emb = _build_ragas_embeddings()

        metrics = [faithfulness, answer_relevancy, context_precision, context_recall]

        try:
            result = evaluate(
                dataset,
                metrics=metrics,
                llm=ragas_llm,
                embeddings=ragas_emb,
                raise_exceptions=False,
            )
            df = result.to_pandas()
            numeric_cols = [c for c in df.columns if c not in ("question", "answer", "contexts", "ground_truth")]
            scores = {}
            for col in numeric_cols:
                try:
                    scores[col] = float(df[col].mean())
                except Exception:
                    pass
            per_sample = df.to_dict(orient="records")
        except Exception as e:
            logger.error("ragas_evaluate_failed", error=str(e))
            scores = {}
            per_sample = []

        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "num_samples": len(test_dataset),
            "scores": scores,
            "per_sample": per_sample,
        }

        out_path = self.output_dir / f"eval_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        out_path.write_text(json.dumps(report, indent=2, default=str))
        logger.info("evaluation_complete", scores=scores, report=str(out_path))
        return report


DEFAULT_TEST_DATASET = [
    {
        "question": "What does it mean when a kiosk shows Offline?",
        "ground_truth": "The kiosk is not currently connected. Actions sent by the agent will not reach the kiosk when it is offline.",
    },
    {
        "question": "How does an agent take control of a device?",
        "ground_truth": "The agent presses the Take Control button, which appears when no other agent is controlling the device.",
    },
    {
        "question": "What is the observer model?",
        "ground_truth": "A kiosk can only be operated by one agent at a time. All other agents viewing that device are observers whose action buttons are blocked.",
    },
    {
        "question": "What steps does a kiosk go through when it starts up?",
        "ground_truth": "The kiosk loads settings, checks it is the only running instance, verifies authorization, loads device settings, validates required configuration, prepares document reading and motion detection, warms up the ID reader, then shows the main screen.",
    },
    {
        "question": "What is Simulation Mode?",
        "ground_truth": "Simulation Mode replaces all physical hardware with simulated versions so agents can test the kiosk without real hardware attached.",
    },
    {
        "question": "How do agents sign in to the dashboard?",
        "ground_truth": "Agents sign in at /login with their Agent ID and password, then select a device from the device-selection screen at /select-device.",
    },
    {
        "question": "What required fields must be filled for the kiosk to start?",
        "ground_truth": "Device Name, Agent Name, Agent Email, Location, Hotel Name, Support Email, Phone, WiFi Name, WiFi Password, Check Out Time, Breakfast Time, Body Notes, Footer Notes, Cash Port, Key Port, Baud Rate, Scanner Option, and the Recycler 1-4 denominations.",
    },
    {
        "question": "What happens when an admin revokes a running kiosk?",
        "ground_truth": "The kiosk shows a message that its access has been removed and that the application will restart, then restarts and lands on the login screen.",
    },
]