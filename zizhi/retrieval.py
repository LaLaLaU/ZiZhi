from __future__ import annotations

import math
import os
import re
from pathlib import Path
from typing import Iterable

from zizhi.corpus import load_corpus
from zizhi.schemas import HistoricalChunk


TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,}|[a-zA-Z0-9_]+")


def tokenize(text: str) -> set[str]:
    compact = text.replace(" ", "")
    tokens = set(TOKEN_PATTERN.findall(text))
    chinese_keywords = [
        "领导",
        "老板",
        "同事",
        "下属",
        "合伙",
        "站队",
        "信任",
        "猜忌",
        "授权",
        "冲突",
        "绕过",
        "压力",
        "委屈",
        "团队",
        "内斗",
        "表态",
        "去留",
        "制衡",
        "联盟",
        "用人",
        "沟通",
    ]
    tokens.update(keyword for keyword in chinese_keywords if keyword in compact)
    return tokens


class HistoricalRetriever:
    def __init__(
        self,
        corpus_path: str | Path | None = None,
        top_k: int = 4,
        enable_lancedb: bool | None = None,
    ) -> None:
        self.chunks = load_corpus(corpus_path)
        self.top_k = top_k
        self.enable_lancedb = (
            os.getenv("ZIZHI_ENABLE_LANCEDB", "0") == "1"
            if enable_lancedb is None
            else enable_lancedb
        )
        self._lance_table = None
        self._embedding_model = None
        if self.enable_lancedb:
            self._try_init_lancedb()

    def search(self, queries: Iterable[str], top_k: int | None = None) -> list[HistoricalChunk]:
        query_list = [query for query in queries if query.strip()]
        if not query_list:
            return []
        if self._lance_table is not None and self._embedding_model is not None:
            try:
                return self._search_lancedb(query_list, top_k or self.top_k)
            except Exception:
                pass
        return self._search_keywords(query_list, top_k or self.top_k)

    def _try_init_lancedb(self) -> None:
        try:
            import lancedb
            from sentence_transformers import SentenceTransformer

            model_name = os.getenv("ZIZHI_EMBEDDING_MODEL", "BAAI/bge-m3")
            self._embedding_model = SentenceTransformer(model_name)
            db_path = Path(os.getenv("ZIZHI_LANCEDB_PATH", ".zizhi_lancedb"))
            db = lancedb.connect(str(db_path))
            rows = []
            for chunk in self.chunks:
                vector = self._embedding_model.encode(chunk.retrieval_text or chunk.text).tolist()
                rows.append({**chunk.model_dump(), "vector": vector})
            self._lance_table = db.create_table("zizhi_chunks", data=rows, mode="overwrite")
        except Exception:
            self._lance_table = None
            self._embedding_model = None

    def _search_lancedb(self, queries: list[str], top_k: int) -> list[HistoricalChunk]:
        merged_query = " ".join(queries)
        vector = self._embedding_model.encode(merged_query).tolist()
        rows = self._lance_table.search(vector).limit(top_k).to_list()
        chunks = []
        for row in rows:
            payload = {key: value for key, value in row.items() if key not in {"vector", "_distance"}}
            distance = float(row.get("_distance", 1.0))
            payload["score"] = max(0.0, 1.0 - distance)
            chunks.append(HistoricalChunk.model_validate(payload))
        return chunks

    def _search_keywords(self, queries: list[str], top_k: int) -> list[HistoricalChunk]:
        query_text = " ".join(queries)
        query_tokens = tokenize(query_text)
        scored: list[HistoricalChunk] = []
        for chunk in self.chunks:
            retrieval_text = chunk.retrieval_text or chunk.white_text or chunk.text
            chunk_tokens = tokenize(
                " ".join(
                    [
                        retrieval_text,
                        chunk.chapter_title,
                        chunk.year,
                        " ".join(chunk.topic_tags),
                        " ".join(chunk.situation_tags),
                    ]
                )
            )
            overlap = len(query_tokens & chunk_tokens)
            tag_bonus = sum(0.25 for tag in chunk.topic_tags + chunk.situation_tags if tag in query_text)
            score = math.log1p(overlap) + tag_bonus + chunk.source_priority * 0.35
            scored.append(chunk.model_copy(update={"score": round(score, 4)}))
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]
