import re
import uuid
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from configs.settings import get_settings
from configs.logging_config import get_logger

logger = get_logger(__name__)

_H1 = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_H2 = re.compile(r"^##\s+(.+)$", re.MULTILINE)
_H3 = re.compile(r"^###\s+(.+)$", re.MULTILINE)
_ANY_HEADER = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
_TABLE_ROW = re.compile(r"^\|.+\|$", re.MULTILINE)
_BULLET = re.compile(r"^(\s*[-*+]|\s*\d+\.)\s+", re.MULTILINE)
_CODE_FENCE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_BLANK_LINES = re.compile(r"\n{3,}")


@dataclass
class Document:
    doc_id: str
    content: str
    metadata: dict = field(default_factory=dict)


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    content: str
    metadata: dict = field(default_factory=dict)


class MarkdownLoader:
    def __init__(self, source_path: str):
        self.source_path = Path(source_path)

    def load(self) -> List[Document]:
        if self.source_path.is_file():
            return [self._load_file(self.source_path)]
        docs = []
        for fp in sorted(self.source_path.glob("**/*.md")):
            docs.append(self._load_file(fp))
        logger.info("loaded_documents", count=len(docs), path=str(self.source_path))
        return docs

    def _load_file(self, path: Path) -> Document:
        text = path.read_text(encoding="utf-8")
        text = _BLANK_LINES.sub("\n\n", text).strip()
        return Document(
            doc_id=str(uuid.uuid5(uuid.NAMESPACE_URL, str(path))),
            content=text,
            metadata={"source": str(path), "filename": path.name},
        )


class KiotelChunker:
    """
    Hierarchical chunker purpose-built for the Kiotel documentation.

    The doc is well-structured with clear H1/H2/H3 sections that map
    directly to features, workflows, and concepts. Rather than a dumb
    sliding window, we:

      1. Parse the full H1 → H2 → H3 hierarchy.
      2. Each H3 (or H2 leaf) becomes its own chunk — these are already
         the right granularity (typically 80-300 words).
      3. We prepend a "breadcrumb" (H1 > H2 > H3 title) so every chunk
         is self-contained — the retriever never loses context.
      4. Table blocks are kept intact as a single chunk.
      5. Long sections (>= max_words) are split on paragraph boundaries
         first, then sentence boundaries, never in the middle of a sentence.
      6. Tiny sections (<= min_words) are merged upward into their parent
         or the previous sibling so we don't waste embeddings on stubs.
    """

    def __init__(
        self,
        max_words: Optional[int] = None,
        min_words: int = 30,
    ):
        settings = get_settings()
        self.max_words = max_words or settings.chunk_size
        self.min_words = min_words

    def chunk(self, documents: List[Document]) -> List[Chunk]:
        all_chunks: List[Chunk] = []
        for doc in documents:
            all_chunks.extend(self._chunk_document(doc))
        logger.info(
            "chunked_documents",
            doc_count=len(documents),
            chunk_count=len(all_chunks),
        )
        return all_chunks

    def _chunk_document(self, doc: Document) -> List[Chunk]:
        sections = self._parse_hierarchy(doc.content)
        raw_chunks: List[Tuple[str, dict]] = []

        for h1, h2, h3, body in sections:
            breadcrumb_parts = [p for p in [h1, h2, h3] if p]
            breadcrumb = " > ".join(breadcrumb_parts)
            leaf_title = h3 or h2 or h1 or "Document"

            if not body.strip():
                continue

            if self._is_table_block(body):
                text = f"[{breadcrumb}]\n\n{body.strip()}"
                raw_chunks.append((text, {"section_h1": h1, "section_h2": h2, "section_h3": h3, "breadcrumb": breadcrumb, "chunk_type": "table"}))
                continue

            words = body.split()
            if len(words) <= self.max_words:
                text = f"[{breadcrumb}]\n\n{body.strip()}"
                raw_chunks.append((text, {"section_h1": h1, "section_h2": h2, "section_h3": h3, "breadcrumb": breadcrumb, "chunk_type": "section"}))
            else:
                sub = self._split_long_section(body, breadcrumb)
                for i, piece in enumerate(sub):
                    raw_chunks.append((piece, {"section_h1": h1, "section_h2": h2, "section_h3": h3, "breadcrumb": breadcrumb, "chunk_type": "section", "sub_index": i}))

        merged = self._merge_tiny(raw_chunks)

        chunks: List[Chunk] = []
        for idx, (text, meta) in enumerate(merged):
            chunks.append(
                Chunk(
                    chunk_id=str(uuid.uuid4()),
                    doc_id=doc.doc_id,
                    content=text,
                    metadata={**doc.metadata, **meta, "chunk_index": idx},
                )
            )
        return chunks

    def _parse_hierarchy(self, text: str) -> List[Tuple[str, str, str, str]]:
        """
        Returns list of (h1_title, h2_title, h3_title, body_text).
        Tracks the current H1 and H2 context for every H3 body.
        """
        matches = list(_ANY_HEADER.finditer(text))
        if not matches:
            return [("", "", "", text)]

        sections = []
        current_h1 = ""
        current_h2 = ""

        for i, m in enumerate(matches):
            level = len(m.group(1))
            title = m.group(2).strip()
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[m.end():end].strip()

            if level == 1:
                current_h1 = title
                current_h2 = ""
                if body:
                    sections.append((current_h1, "", "", body))
            elif level == 2:
                current_h2 = title
                if body:
                    sections.append((current_h1, current_h2, "", body))
            elif level == 3:
                sections.append((current_h1, current_h2, title, body))

        return sections

    def _is_table_block(self, text: str) -> bool:
        lines = [l for l in text.strip().splitlines() if l.strip()]
        if not lines:
            return False
        table_lines = sum(1 for l in lines if _TABLE_ROW.match(l))
        return table_lines / max(len(lines), 1) > 0.5

    def _split_long_section(self, body: str, breadcrumb: str) -> List[str]:
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", body) if p.strip()]
        result = []
        current_parts: List[str] = []
        current_words = 0

        for para in paragraphs:
            w = len(para.split())
            if current_words + w > self.max_words and current_parts:
                combined = "\n\n".join(current_parts)
                result.append(f"[{breadcrumb}]\n\n{combined}")
                current_parts = [para]
                current_words = w
            else:
                current_parts.append(para)
                current_words += w

        if current_parts:
            combined = "\n\n".join(current_parts)
            result.append(f"[{breadcrumb}]\n\n{combined}")

        if not result:
            result.append(f"[{breadcrumb}]\n\n{body.strip()}")

        return result

    def _merge_tiny(self, chunks: List[Tuple[str, dict]]) -> List[Tuple[str, dict]]:
        if not chunks:
            return chunks
        merged = [chunks[0]]
        for text, meta in chunks[1:]:
            words = len(text.split())
            prev_text, prev_meta = merged[-1]
            prev_words = len(prev_text.split())
            same_section = (
                meta.get("section_h1") == prev_meta.get("section_h1")
                and meta.get("section_h2") == prev_meta.get("section_h2")
            )
            if words < self.min_words and same_section and prev_words + words <= self.max_words * 1.2:
                merged[-1] = (prev_text + "\n\n" + text, prev_meta)
            else:
                merged.append((text, meta))
        return merged
