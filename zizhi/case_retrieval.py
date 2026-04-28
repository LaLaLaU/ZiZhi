from __future__ import annotations

import hashlib
import json
import math
import os
import re
from pathlib import Path
from typing import Any
from typing import Iterable

from zizhi.corpus import load_case_profile_corpus, load_tagging_chunk_corpus
from zizhi.retrieval import _extract_query_terms, tokenize
from zizhi.schemas import CaseProfile, HistoricalChunk, RetrievedCase


CASE_QUERY_NOISE = {
    "怎么办",
    "如何处理",
    "怎么处理",
    "如何管理",
    "怎么管理",
    "如何应对",
    "怎么应对",
    "有关",
    "相关",
    "案例",
    "史例",
    "问题",
}


class CaseRetriever:
    def __init__(
        self,
        cases: list[CaseProfile] | None = None,
        chunks: list[HistoricalChunk] | None = None,
        top_k: int = 4,
        enable_dense: bool | None = None,
        rrf_k: int = 60,
    ) -> None:
        self.cases = cases if cases is not None else load_case_profile_corpus()
        self.chunks = chunks if chunks is not None else load_tagging_chunk_corpus()
        self.top_k = top_k
        self.rrf_k = rrf_k
        self.enable_dense = (
            os.getenv("ZIZHI_CASE_ENABLE_DENSE", "1") == "1"
            if enable_dense is None
            else enable_dense
        )
        self.status: dict[str, Any] = {
            "dense_requested": self.enable_dense,
            "dense_backend_ready": False,
            "backend_mode": "sparse-only" if not self.enable_dense else "dense-initializing",
            "embedding_model": os.getenv("ZIZHI_CASE_EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5"),
            "lancedb_path": os.getenv("ZIZHI_CASE_LANCEDB_PATH", ".zizhi_case_lancedb"),
            "lancedb_table": os.getenv("ZIZHI_CASE_LANCEDB_TABLE", "zizhi_cases_dense"),
            "index_status": "not_requested" if not self.enable_dense else "initializing",
            "case_count": 0,
            "error": "",
        }
        self.chunk_by_id = {chunk.chunk_id: chunk for chunk in self.chunks}
        self._dense_backend = None
        self._indexed_cases = [_index_case(case) for case in self.cases]
        self._indexed_case_by_id = {indexed["case_id"]: indexed for indexed in self._indexed_cases}
        self.status["case_count"] = len(self._indexed_cases)
        if self.enable_dense:
            self._try_init_dense_backend()
        self._log_status()

    def search(self, queries: Iterable[str], top_k: int | None = None) -> list[RetrievedCase]:
        query_list = [query.strip() for query in queries if query and query.strip()]
        if not query_list or not self._indexed_cases:
            return []

        limit = max(top_k or self.top_k, 1)
        branch_limit = max(limit * 4, 12)
        sparse_results = self._search_sparse(query_list, branch_limit)
        dense_results = self._search_dense(query_list, branch_limit)
        fused = _rrf_fuse([("sparse", sparse_results), ("dense", dense_results)], top_k=limit, rrf_k=self.rrf_k)
        return fused[:limit]

    def expand_cases_to_chunks(
        self,
        cases: list[RetrievedCase],
        per_case_top_k: int = 2,
        max_chunks: int = 6,
    ) -> list[HistoricalChunk]:
        if not cases:
            return []

        expanded: list[HistoricalChunk] = []
        seen_chunk_ids: set[str] = set()
        for case in cases:
            used = 0
            for chunk_id in case.chunk_ids:
                if chunk_id in seen_chunk_ids:
                    continue
                chunk = self.chunk_by_id.get(chunk_id)
                if chunk is None:
                    continue
                expanded.append(chunk.model_copy(update={"score": round(case.retrieval_score, 4)}))
                seen_chunk_ids.add(chunk_id)
                used += 1
                if used >= per_case_top_k or len(expanded) >= max_chunks:
                    break
            if len(expanded) >= max_chunks:
                break
        return expanded

    def _try_init_dense_backend(self) -> None:
        try:
            import numpy as np
            from sentence_transformers import SentenceTransformer

            model_name = os.getenv("ZIZHI_CASE_EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")
            model = SentenceTransformer(model_name)
            signature = _build_case_signature(self._indexed_cases)
            dense_path = Path(os.getenv("ZIZHI_CASE_DENSE_CACHE_PATH", ".cache/case_dense_vectors"))
            table_name = os.getenv("ZIZHI_CASE_LANCEDB_TABLE", "zizhi_cases_dense")
            vectors_path = dense_path / f"{table_name}.npy"
            ids_path = dense_path / f"{table_name}.ids.json"
            meta_path = dense_path / f"{table_name}.meta.json"
            dense_path.mkdir(parents=True, exist_ok=True)

            backend_mode = "local-vector-cache"
            index_status = "reused"
            case_ids = [indexed["case_id"] for indexed in self._indexed_cases]
            vectors = None

            if _is_local_dense_cache_current(meta_path, signature, model_name, len(self._indexed_cases), ids_path, vectors_path):
                vectors = np.load(vectors_path)
                cached_case_ids = json.loads(ids_path.read_text(encoding="utf-8"))
                if cached_case_ids != case_ids:
                    vectors = None
                else:
                    index_status = "reused"

            if vectors is None:
                _backup_dense_cache(dense_path, table_name)
                dense_texts = [indexed["dense_text"] for indexed in self._indexed_cases]
                vectors = model.encode(dense_texts, normalize_embeddings=True, show_progress_bar=True)
                np.save(vectors_path, vectors)
                ids_path.write_text(json.dumps(case_ids, ensure_ascii=False, indent=2), encoding="utf-8")
                _write_dense_index_meta(
                    meta_path=meta_path,
                    signature=signature,
                    model_name=model_name,
                    case_count=len(self._indexed_cases),
                )
                index_status = "rebuilt"

            self._dense_backend = {
                "model": model,
                "model_name": model_name,
                "vectors": vectors,
                "case_ids": case_ids,
                "cache_dir": str(dense_path),
            }
            self.status.update(
                {
                    "dense_backend_ready": True,
                    "backend_mode": backend_mode,
                    "embedding_model": model_name,
                    "lancedb_path": str(dense_path),
                    "lancedb_table": table_name,
                    "index_status": index_status,
                    "error": "",
                }
            )
        except Exception as vector_exc:
            try:
                import lancedb
                from sentence_transformers import SentenceTransformer

                model_name = os.getenv("ZIZHI_CASE_EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")
                db_path = Path(os.getenv("ZIZHI_CASE_LANCEDB_PATH", ".zizhi_case_lancedb"))
                table_name = os.getenv("ZIZHI_CASE_LANCEDB_TABLE", "zizhi_cases_dense")
                model = SentenceTransformer(model_name)
                db = lancedb.connect(str(db_path))
                signature = _build_case_signature(self._indexed_cases)
                meta_path = db_path / f"{table_name}.meta.json"

                if _is_dense_index_current(db, table_name, meta_path, signature, model_name, len(self._indexed_cases)):
                    table = db.open_table(table_name)
                    index_status = "reused"
                else:
                    rows = []
                    for indexed in self._indexed_cases:
                        case: CaseProfile = indexed["case"]
                        vector = model.encode(indexed["dense_text"], normalize_embeddings=True).tolist()
                        rows.append(
                            {
                                "case_id": case.case_id,
                                "title": case.title,
                                "dense_text": indexed["dense_text"],
                                "vector": vector,
                            }
                        )
                    table = db.create_table(table_name, data=rows, mode="overwrite")
                    _write_dense_index_meta(
                        meta_path=meta_path,
                        signature=signature,
                        model_name=model_name,
                        case_count=len(self._indexed_cases),
                    )
                    index_status = "rebuilt"

                self._dense_backend = {
                    "db": db,
                    "table": table,
                    "model": model,
                    "model_name": model_name,
                    "table_name": table_name,
                }
                self.status.update(
                    {
                        "dense_backend_ready": True,
                        "backend_mode": "lancedb-vector",
                        "embedding_model": model_name,
                        "lancedb_path": str(db_path),
                        "lancedb_table": table_name,
                        "index_status": index_status,
                        "error": "",
                    }
                )
            except Exception as exc:
                self._dense_backend = None
                self.status.update(
                    {
                        "dense_backend_ready": False,
                        "backend_mode": "dense-fallback",
                        "index_status": "failed",
                        "error": f"local_cache_error={type(vector_exc).__name__}: {vector_exc}; lancedb_error={type(exc).__name__}: {exc}",
                    }
                )

    def _search_sparse(self, queries: list[str], top_k: int) -> list[RetrievedCase]:
        query_text = " ".join(queries)
        query_tokens = tokenize(query_text)
        query_terms = _clean_case_query_terms(_extract_query_terms(queries))
        scored: list[RetrievedCase] = []
        for indexed in self._indexed_cases:
            overlap = len(query_tokens & indexed["sparse_tokens"])
            exact_bonus = _exact_term_bonus(query_terms, indexed["sparse_compact"], long_bonus=1.15, short_bonus=0.75, cap=4.8)
            tag_bonus = sum(0.45 for tag in indexed["case_tags"] if tag and tag in query_text)
            role_bonus = sum(0.4 for role in indexed["actor_roles"] if role and role in query_text)
            perspective_bonus = sum(0.35 for summary in indexed["perspective_summaries"] if summary and any(term in summary for term in query_terms))
            type_bonus = 0.25 if indexed["case_type"] and indexed["case_type"] in query_text else 0.0
            score = math.log1p(overlap) + exact_bonus + tag_bonus + role_bonus + perspective_bonus + type_bonus + indexed["source_priority"] * 0.3
            if score <= 0:
                continue
            scored.append(
                _build_retrieved_case(
                    indexed=indexed,
                    score=score,
                    retrieval_text=indexed["sparse_text"],
                    matched_terms=[term for term in query_terms if term in indexed["sparse_compact"]][:6],
                    matched_fields=_matched_sparse_fields(indexed, query_terms, query_text),
                )
            )
        scored.sort(key=lambda item: item.retrieval_score, reverse=True)
        return scored[:top_k]

    def _search_dense(self, queries: list[str], top_k: int) -> list[RetrievedCase]:
        if self._dense_backend is not None:
            return self._search_dense_vector(queries, top_k)
        return self._search_dense_fallback(queries, top_k)

    def _search_dense_vector(self, queries: list[str], top_k: int) -> list[RetrievedCase]:
        backend = self._dense_backend
        if backend is None:
            return []

        if "vectors" in backend:
            return self._search_dense_local_cache(queries, top_k)

        query_terms = _clean_case_query_terms(_extract_query_terms(queries))
        best_by_case: dict[str, tuple[float, dict]] = {}
        model = backend["model"]
        table = backend["table"]
        for query in queries:
            vector = model.encode(query, normalize_embeddings=True).tolist()
            rows = table.search(vector).metric("cosine").limit(top_k).to_list()
            for row in rows:
                case_id = str(row.get("case_id", "")).strip()
                if not case_id:
                    continue
                distance = float(row.get("_distance", 1.0))
                score = max(0.0, 1.0 - distance)
                if case_id not in best_by_case or score > best_by_case[case_id][0]:
                    indexed = self._indexed_case_by_id.get(case_id)
                    if indexed is not None:
                        best_by_case[case_id] = (score, indexed)

        scored: list[RetrievedCase] = []
        for score, indexed in best_by_case.values():
            scored.append(
                _build_retrieved_case(
                    indexed=indexed,
                    score=score,
                    retrieval_text=indexed["dense_text"],
                    matched_terms=[term for term in query_terms if term in indexed["dense_compact"]][:6],
                    matched_fields=_matched_dense_fields(indexed, query_terms),
                )
            )
        scored.sort(key=lambda item: item.retrieval_score, reverse=True)
        return scored[:top_k]

    def _search_dense_local_cache(self, queries: list[str], top_k: int) -> list[RetrievedCase]:
        import numpy as np

        backend = self._dense_backend
        if backend is None:
            return []

        vectors = backend["vectors"]
        model = backend["model"]

        # 逐条编码，每个 case 取所有查询中的最高分
        query_vectors = model.encode(queries, normalize_embeddings=True)
        per_query_scores = np.dot(vectors, query_vectors.T)  # shape: (n_cases, n_queries)
        scores = per_query_scores.max(axis=1)

        top_indices = np.argsort(scores)[::-1][:top_k]
        query_terms = _clean_case_query_terms(_extract_query_terms(queries))
        scored: list[RetrievedCase] = []
        for index in top_indices:
            case_id = backend["case_ids"][int(index)]
            indexed = self._indexed_case_by_id.get(case_id)
            if indexed is None:
                continue
            score = float(scores[int(index)])
            scored.append(
                _build_retrieved_case(
                    indexed=indexed,
                    score=score,
                    retrieval_text=indexed["dense_text"],
                    matched_terms=[term for term in query_terms if term in indexed["dense_compact"]][:6],
                    matched_fields=_matched_dense_fields(indexed, query_terms),
                )
            )
        scored.sort(key=lambda item: item.retrieval_score, reverse=True)
        return scored[:top_k]

    def _search_dense_fallback(self, queries: list[str], top_k: int) -> list[RetrievedCase]:
        query_text = " ".join(queries)
        query_tokens = tokenize(query_text)
        query_terms = _clean_case_query_terms(_extract_query_terms(queries))
        scored: list[RetrievedCase] = []
        for indexed in self._indexed_cases:
            overlap = len(query_tokens & indexed["dense_tokens"])
            exact_bonus = _exact_term_bonus(query_terms, indexed["dense_compact"], long_bonus=1.35, short_bonus=0.9, cap=5.0)
            phrase_bonus = 0.8 if any(term in indexed["dense_text"] for term in query_terms if len(term) >= 3) else 0.0
            score = math.log1p(overlap) + exact_bonus + phrase_bonus + indexed["source_priority"] * 0.25
            if score <= 0:
                continue
            scored.append(
                _build_retrieved_case(
                    indexed=indexed,
                    score=score,
                    retrieval_text=indexed["dense_text"],
                    matched_terms=[term for term in query_terms if term in indexed["dense_compact"]][:6],
                    matched_fields=_matched_dense_fields(indexed, query_terms),
                )
            )
        scored.sort(key=lambda item: item.retrieval_score, reverse=True)
        return scored[:top_k]

    def status_summary(self) -> str:
        mode = self.status.get("backend_mode", "unknown")
        model = self.status.get("embedding_model", "")
        index_status = self.status.get("index_status", "unknown")
        cache_path = self.status.get("lancedb_path", "")
        if mode == "lancedb-vector":
            return f"case dense 已启用：{model} / LanceDB / index={index_status}"
        if mode == "local-vector-cache":
            return f"case dense 已启用：{model} / local vector cache / index={index_status} / path={cache_path}"
        if self.enable_dense:
            error = self.status.get("error", "")
            return f"case dense 已降级：fallback lexical（原因：{error or 'unknown'}）"
        return "case dense 未启用：当前使用 sparse-only / lexical fallback"

    def _log_status(self) -> None:
        print(f"[CaseRetriever] {self.status_summary()}")


def _index_case(case: CaseProfile) -> dict:
    dense_text = _build_dense_text(case)
    sparse_text = _build_sparse_text(case)
    case_tags = [tag.strip() for tag in case.case_tags if tag.strip()]
    actor_roles = [actor.role.strip() for actor in case.actors if actor.role.strip()]
    perspective_summaries = [
        perspective.perspective_summary.strip()
        for perspective in case.perspectives
        if perspective.perspective_summary.strip()
    ]
    return {
        "case": case,
        "case_id": case.case_id,
        "dense_text": dense_text,
        "dense_compact": _compact_text(dense_text),
        "dense_tokens": tokenize(dense_text),
        "sparse_text": sparse_text,
        "sparse_compact": _compact_text(sparse_text),
        "sparse_tokens": tokenize(sparse_text),
        "case_tags": case_tags,
        "actor_roles": actor_roles,
        "perspective_summaries": perspective_summaries,
        "case_type": case.case_type,
        "source_priority": case.source_priority or 0.5,
    }


def _build_dense_text(case: CaseProfile) -> str:
    title = case.title.strip()
    summary = case.summary.strip()
    core_conflict = case.core_conflict.strip()
    pattern = case.transferable_pattern.strip()
    # 通过重复给 title 和 pattern 更高权重（向量编码中文本越长，对最终向量的影响越大）
    # title 2x + pattern 2x + summary 1x + conflict 1x
    parts = [title, title, pattern, pattern, summary, core_conflict]
    return "\n".join(part for part in parts if part)


def _build_sparse_text(case: CaseProfile) -> str:
    parts = [
        case.title.strip(),
        case.summary.strip(),
        case.core_conflict.strip(),
        case.decision_actor.strip(),
        case.case_type.strip(),
        " ".join(tag.strip() for tag in case.case_tags if tag.strip()),
        " ".join(actor.role.strip() for actor in case.actors if actor.role.strip()),
        " ".join(
            perspective.perspective_summary.strip()
            for perspective in case.perspectives
            if perspective.perspective_summary.strip()
        ),
    ]
    return "\n".join(part for part in parts if part)


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _clean_case_query_terms(terms: Iterable[str]) -> list[str]:
    cleaned: list[str] = []
    for term in terms:
        normalized = term.strip().lower()
        if not normalized or normalized in CASE_QUERY_NOISE:
            continue
        cleaned.append(normalized)
    return sorted(set(cleaned), key=len, reverse=True)


def _exact_term_bonus(
    query_terms: list[str],
    compact_text: str,
    long_bonus: float,
    short_bonus: float,
    cap: float,
) -> float:
    bonus = 0.0
    for term in query_terms:
        if term and term in compact_text:
            bonus += long_bonus if len(term) >= 3 else short_bonus
    return min(bonus, cap)


def _matched_sparse_fields(indexed: dict, query_terms: list[str], query_text: str) -> list[str]:
    fields: list[str] = []
    if any(term in indexed["sparse_compact"] for term in query_terms):
        fields.append("案例细节")
    if any(tag in query_text for tag in indexed["case_tags"]):
        fields.append("案例标签")
    if any(role in query_text for role in indexed["actor_roles"]):
        fields.append("现代角色")
    if any(summary and any(term in summary for term in query_terms) for summary in indexed["perspective_summaries"]):
        fields.append("视角摘要")
    if indexed["case_type"] and indexed["case_type"] in query_text:
        fields.append("案例类型")
    return fields or ["关键词线索"]


def _matched_dense_fields(indexed: dict, query_terms: list[str]) -> list[str]:
    fields: list[str] = []
    if any(term in _compact_text(indexed["case"].transferable_pattern) for term in query_terms):
        fields.append("可迁移模式")
    if any(term in _compact_text(indexed["case"].title) for term in query_terms):
        fields.append("案例标题")
    return fields or ["语义主线"]


def _build_retrieved_case(
    indexed: dict,
    score: float,
    retrieval_text: str,
    matched_terms: list[str],
    matched_fields: list[str],
) -> RetrievedCase:
    case: CaseProfile = indexed["case"]
    return RetrievedCase(
        case_id=case.case_id,
        title=case.title,
        summary=case.summary,
        case_type=case.case_type,
        section_keys=case.section_keys,
        chunk_ids=case.chunk_ids,
        decision_actor=case.decision_actor,
        core_conflict=case.core_conflict,
        transferable_pattern=case.transferable_pattern,
        case_tags=[tag.strip() for tag in case.case_tags if tag.strip()],
        actor_roles=[actor.role.strip() for actor in case.actors if actor.role.strip()],
        retrieval_score=round(score, 4),
        retrieval_text=retrieval_text,
        matched_terms=matched_terms,
        matched_fields=matched_fields,
        mapping_reason=_build_mapping_reason(case, matched_fields, matched_terms),
        source_priority=case.source_priority,
    )


def _build_mapping_reason(case: CaseProfile, matched_fields: list[str], matched_terms: list[str]) -> str:
    field_text = "、".join(matched_fields[:3]) if matched_fields else "案例结构"
    term_text = "、".join(matched_terms[:4]) if matched_terms else case.case_type
    pattern = case.transferable_pattern.strip() or case.summary.strip() or case.title.strip()
    pattern = pattern[:88] + "..." if len(pattern) > 88 else pattern
    return f"该案例通过{field_text}与当前问题形成对应；命中线索包括「{term_text}」。其可迁移主线是：{pattern}"


def _rrf_fuse(
    ranked_lists: list[tuple[str, list[RetrievedCase]]],
    top_k: int,
    rrf_k: int,
) -> list[RetrievedCase]:
    merged: dict[str, dict] = {}
    for source_name, results in ranked_lists:
        for rank, result in enumerate(results, start=1):
            row = merged.setdefault(
                result.case_id,
                {
                    "case": result,
                    "rrf_score": 0.0,
                    "matched_terms": set(result.matched_terms),
                    "matched_fields": set(result.matched_fields),
                    "mapping_reasons": [f"{source_name}:{result.mapping_reason}"],
                },
            )
            row["rrf_score"] += 1.0 / (rrf_k + rank)
            row["matched_terms"].update(result.matched_terms)
            row["matched_fields"].update(result.matched_fields)
            row["mapping_reasons"].append(f"{source_name}:{result.mapping_reason}")
            if result.retrieval_score > row["case"].retrieval_score:
                row["case"] = result

    fused: list[RetrievedCase] = []
    for row in merged.values():
        case = row["case"]
        mapping_reason = _merge_mapping_reasons(row["mapping_reasons"])
        fused.append(
            case.model_copy(
                update={
                    "retrieval_score": round(row["rrf_score"], 6),
                    "matched_terms": sorted(row["matched_terms"], key=len, reverse=True)[:8],
                    "matched_fields": sorted(row["matched_fields"]),
                    "mapping_reason": mapping_reason,
                }
            )
        )
    fused.sort(key=lambda item: item.retrieval_score, reverse=True)
    return fused[:top_k]


def _merge_mapping_reasons(reasons: list[str]) -> str:
    cleaned = [reason.split(":", 1)[1] for reason in reasons if ":" in reason]
    if not cleaned:
        return ""
    unique = []
    seen: set[str] = set()
    for reason in cleaned:
        if reason in seen:
            continue
        seen.add(reason)
        unique.append(reason)
    return unique[0]


def _build_case_signature(indexed_cases: list[dict]) -> str:
    payload = [
        {
            "case_id": indexed["case_id"],
            "dense_text": indexed["dense_text"],
        }
        for indexed in indexed_cases
    ]
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _is_dense_index_current(
    db,
    table_name: str,
    meta_path: Path,
    signature: str,
    model_name: str,
    case_count: int,
) -> bool:
    try:
        if not meta_path.exists():
            return False
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("signature") != signature:
            return False
        if meta.get("model_name") != model_name:
            return False
        if int(meta.get("case_count", -1)) != case_count:
            return False
        db.open_table(table_name)
        return True
    except Exception:
        return False


def _backup_dense_cache(dense_path: Path, table_name: str) -> None:
    """重建前将旧缓存备份为带版本号的文件，如 v1.npy、v2.npy……"""
    src_files = [
        dense_path / f"{table_name}.npy",
        dense_path / f"{table_name}.ids.json",
        dense_path / f"{table_name}.meta.json",
    ]
    if not all(f.exists() for f in src_files):
        return
    existing = sorted(dense_path.glob(f"{table_name}_v*.npy"))
    next_ver = len(existing) + 1
    for src in src_files:
        suffix = src.suffix
        stem = src.stem  # e.g. "zizhi_cases_dense"
        backup = dense_path / f"{stem}_v{next_ver}{suffix}"
        src.rename(backup)


def _is_local_dense_cache_current(
    meta_path: Path,
    signature: str,
    model_name: str,
    case_count: int,
    ids_path: Path,
    vectors_path: Path,
) -> bool:
    try:
        if not meta_path.exists() or not ids_path.exists() or not vectors_path.exists():
            return False
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("signature") != signature:
            return False
        if meta.get("model_name") != model_name:
            return False
        if int(meta.get("case_count", -1)) != case_count:
            return False
        return True
    except Exception:
        return False


def _write_dense_index_meta(
    meta_path: Path,
    signature: str,
    model_name: str,
    case_count: int,
) -> None:
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(
        json.dumps(
            {
                "signature": signature,
                "model_name": model_name,
                "case_count": case_count,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
