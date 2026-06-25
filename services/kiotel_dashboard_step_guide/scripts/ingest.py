import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from configs.settings import get_settings
from configs.logging_config import get_logger
from src.ingestion.loader import MarkdownLoader, KiotelChunker
from src.retrieval.vector_store import VectorStore
from src.retrieval.bm25_index import BM25Index

logger = get_logger("ingest")


def run():
    settings = get_settings()
    logger.info("ingestion_start", data_dir=settings.data_dir)

    loader = MarkdownLoader(settings.data_dir)
    documents = loader.load()
    if not documents:
        logger.error("no_documents_found", path=settings.data_dir)
        sys.exit(1)

    chunker = KiotelChunker(
        max_words=settings.chunk_size,
        min_words=settings.chunk_min_words,
    )
    chunks = chunker.chunk(documents)
    logger.info("chunks_created", count=len(chunks))

    logger.info("building_vector_store")
    vs = VectorStore()
    vs.delete_all()
    vs.add_chunks(chunks)
    logger.info("vector_store_ready", total=vs.count())

    logger.info("building_bm25_index")
    bm25 = BM25Index()
    bm25.build(chunks)
    logger.info("bm25_index_ready")

    logger.info("ingestion_complete", chunks=len(chunks))


if __name__ == "__main__":
    run()
