from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from models.deal import Deal

logger = logging.getLogger(__name__)

EmbeddingFn = Callable[[str], list[float]]

DEFAULT_DB_PATH = Path("data/knowledge")
DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"
FALLBACK_DIMENSIONS = 384


class KnowledgeBase:
    def __init__(
        self,
        db_path: Path = DEFAULT_DB_PATH,
        embedding_model: str = DEFAULT_MODEL_NAME,
        embedding_fn: EmbeddingFn | None = None,
        prefer_lancedb: bool = True,
    ) -> None:
        self.db_path = db_path
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.embedding_model = embedding_model
        self._embedding_fn = embedding_fn or self._load_embedding_model(embedding_model)
        self._json_path = self.db_path / "knowledge.json"
        self._db: Any | None = None
        self._table: Any | None = None
        self._use_lancedb = False
        if prefer_lancedb:
            self._connect_lancedb()

    @property
    def available(self) -> bool:
        return True

    def add_destination_info(self, city: str, country: str, info_text: str) -> None:
        documents = [
            self._document(
                text=chunk,
                kind="destination",
                city=city,
                country=country,
                source_id=f"destination:{country}:{city}:{index}",
            )
            for index, chunk in enumerate(_chunk_text(info_text))
        ]
        self._add_documents(documents)

    def add_deal_history(self, deal: Deal) -> None:
        price_yuan = deal.price_cny_fen / 100
        text = (
            f"Historical deal: {deal.origin_city} to {deal.destination_city}, "
            f"{deal.transport_mode.value}, CNY {price_yuan:.0f}, "
            f"departure {deal.departure_date}, "
            f"return {deal.return_date or 'none'}, "
            f"operator {deal.operator or 'unknown'}, "
            f"booking {deal.booking_url}."
        )
        self._add_documents(
            [
                self._document(
                    text=text,
                    kind="deal_history",
                    city=deal.destination_city,
                    country=deal.destination_country or "",
                    source_id=f"deal:{deal.id}",
                )
            ]
        )

    def search(self, query: str, top_k: int = 5) -> list[str]:
        if top_k <= 0:
            return []
        vector = self._embedding_fn(query)
        if self._use_lancedb and self._table is not None:
            try:
                rows = self._table.search(vector).limit(top_k).to_list()
                return [str(row["text"]) for row in rows if row.get("text")]
            except Exception:
                logger.exception("LanceDB search failed; falling back to local JSON search")
        return [
            item["text"]
            for item in sorted(
                self._load_json_documents(),
                key=lambda item: _cosine_similarity(vector, item["vector"]),
                reverse=True,
            )[:top_k]
        ]

    def _add_documents(self, documents: list[dict[str, Any]]) -> None:
        if not documents:
            return
        if self._use_lancedb and self._table is not None:
            try:
                self._table.add(documents)
            except Exception:
                logger.exception("LanceDB add failed; writing documents to local JSON fallback")
        self._add_json_documents(documents)

    def _document(
        self,
        text: str,
        kind: str,
        city: str,
        country: str,
        source_id: str,
    ) -> dict[str, Any]:
        return {
            "id": _stable_id(source_id, text),
            "text": text,
            "vector": self._embedding_fn(text),
            "kind": kind,
            "city": city,
            "country": country,
            "source_id": source_id,
            "created_at": datetime.now(UTC).isoformat(),
        }

    def _connect_lancedb(self) -> None:
        try:
            import lancedb
        except Exception as exc:
            logger.info("LanceDB unavailable; using local JSON knowledge store: %s", exc)
            return

        try:
            self._db = lancedb.connect(str(self.db_path))
            table_names = (
                self._db.list_tables()
                if hasattr(self._db, "list_tables")
                else self._db.table_names()
            )
            if "knowledge" in table_names:
                self._table = self._db.open_table("knowledge")
            else:
                seed = self._document(
                    text="BudgetWings knowledge base initialization record.",
                    kind="system",
                    city="",
                    country="",
                    source_id="system:init",
                )
                try:
                    self._table = self._db.create_table("knowledge", data=[seed])
                except ValueError as exc:
                    if "already exists" not in str(exc).casefold():
                        raise
                    self._table = self._db.open_table("knowledge")
            self._use_lancedb = True
        except Exception:
            logger.exception("Failed to initialize LanceDB; using local JSON fallback")

    def _load_embedding_model(self, embedding_model: str) -> EmbeddingFn:
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as exc:
            logger.info("sentence-transformers unavailable; using hash embeddings: %s", exc)
            return _hash_embedding

        try:
            model = SentenceTransformer(embedding_model)
        except Exception as exc:
            logger.warning("Embedding model unavailable; using hash embeddings: %s", exc)
            return _hash_embedding

        def embed(text: str) -> list[float]:
            vector = model.encode(text, normalize_embeddings=True)
            return [float(value) for value in vector.tolist()]

        return embed

    def _load_json_documents(self) -> list[dict[str, Any]]:
        if not self._json_path.exists():
            return []
        try:
            payload = json.loads(self._json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Invalid JSON knowledge fallback store: %s", self._json_path)
            return []
        if not isinstance(payload, list):
            return []
        return [item for item in payload if _is_document(item)]

    def _add_json_documents(self, documents: list[dict[str, Any]]) -> None:
        existing = {item["id"]: item for item in self._load_json_documents()}
        for document in documents:
            existing[document["id"]] = document
        self._json_path.write_text(
            json.dumps(list(existing.values()), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def _chunk_text(text: str, max_chars: int = 800, overlap: int = 120) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    if len(cleaned) <= max_chars:
        return [cleaned]
    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(start + max_chars, len(cleaned))
        chunks.append(cleaned[start:end].strip())
        if end == len(cleaned):
            break
        start = max(0, end - overlap)
    return chunks


def _hash_embedding(text: str) -> list[float]:
    vector = [0.0] * FALLBACK_DIMENSIONS
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", text.casefold())
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % FALLBACK_DIMENSIONS
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    return sum(left[index] * right[index] for index in range(size))


def _stable_id(source_id: str, text: str) -> str:
    digest = hashlib.sha256(f"{source_id}:{text}".encode()).hexdigest()
    return digest[:32]


def _is_document(item: object) -> bool:
    return (
        isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and isinstance(item.get("text"), str)
        and isinstance(item.get("vector"), list)
    )
