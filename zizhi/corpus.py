from __future__ import annotations

import json
import os
from pathlib import Path

from zizhi.epub_ingest import load_chunks_jsonl, parse_epub_to_chunks, write_chunks_jsonl
from zizhi.schemas import HistoricalChunk
from zizhi.txt_ingest import parse_txt_corpus_to_chunks, write_chunks_jsonl as write_txt_chunks_jsonl


DEFAULT_CACHE_PATH = Path(".cache") / "zizhi_corpus_chunks.jsonl"


SEED_CORPUS: list[HistoricalChunk] = [
    HistoricalChunk(
        chunk_id="seed-xin-001",
        volume="周纪",
        dynasty="战国",
        chapter_title="商鞅立信",
        chunk_type="chen_guang_yue",
        original_text="臣光曰：夫信者，人君之大宝也。国保于民，民保于信。",
        white_text="司马光借立信之事说明，治理与组织秩序依靠可信承诺维系。",
        text="信任 承诺 治理 组织秩序 上下级 失信 取信 司马光 臣光曰",
        people=["司马光", "商鞅"],
        events=["立信取信", "承诺建立秩序"],
        topic_tags=["信任", "治理", "秩序"],
        situation_tags=["君臣", "试探", "取信"],
        source_priority=0.92,
    ),
    HistoricalChunk(
        chunk_id="seed-zhibo-001",
        volume="周纪",
        dynasty="战国",
        chapter_title="智伯亡身",
        chunk_type="chen_guang_yue",
        original_text="臣光曰：智伯之亡也，才胜德也。",
        white_text="智伯有才而失德，刚愎逼迫盟友，最终引发反噬。",
        text="智伯 才胜德 联盟 逼迫 合伙 控制权 盟友反噬 权力失衡",
        people=["智伯", "赵襄子", "韩康子", "魏桓子"],
        events=["智伯索地", "韩魏倒戈", "联盟反噬"],
        topic_tags=["权力", "联盟", "制衡"],
        situation_tags=["结盟", "对立", "控制权"],
        source_priority=0.95,
    ),
    HistoricalChunk(
        chunk_id="seed-taizong-001",
        volume="唐纪",
        dynasty="唐",
        chapter_title="唐太宗纳谏",
        chunk_type="original",
        original_text="兼听则明，偏信则暗。",
        white_text="唐太宗与魏徵讨论纳谏，强调不能只听单一来源，需交叉验证。",
        text="唐太宗 魏徵 纳谏 兼听 偏信 多方信息 向上沟通 决策校验",
        people=["唐太宗", "魏徵"],
        events=["纳谏", "多方听取意见"],
        topic_tags=["沟通", "判断", "信任"],
        situation_tags=["君臣", "进谏", "制衡"],
        source_priority=0.9,
    ),
    HistoricalChunk(
        chunk_id="seed-ma-su-001",
        volume="魏纪",
        dynasty="三国",
        chapter_title="诸葛亮斩马谡",
        chunk_type="original",
        original_text="亮既诛马谡及将军张休、李盛，夺将军黄袭等兵。",
        white_text="街亭失守后，诸葛亮处理责任人，强调关键岗位不能只凭亲近与口才。",
        text="诸葛亮 马谡 街亭 用人 授权 责任 关键岗位 团队纪律",
        people=["诸葛亮", "马谡"],
        events=["街亭失守", "用人失察", "追究责任"],
        topic_tags=["用人", "授权", "风险"],
        situation_tags=["上下级", "问责", "授权"],
        source_priority=0.84,
    ),
    HistoricalChunk(
        chunk_id="seed-guangwu-001",
        volume="汉纪",
        dynasty="东汉",
        chapter_title="光武用人",
        chunk_type="commentary",
        annotation_text="以功臣守位，以文吏治事，功名与职分分开，减少旧部掣肘。",
        white_text="光武帝稳定局势时，既安置功臣，又让具体治理回到制度和职责。",
        text="光武帝 功臣 文吏 用人 授权 制度 组织变革 功高难制",
        people=["光武帝", "功臣", "文吏"],
        events=["安置功臣", "职责分工", "组织稳定"],
        topic_tags=["用人", "组织", "制衡"],
        situation_tags=["君臣", "授权", "制衡"],
        source_priority=0.76,
    ),
    HistoricalChunk(
        chunk_id="seed-liu-bei-001",
        volume="汉纪",
        dynasty="三国",
        chapter_title="刘备托孤",
        chunk_type="original",
        original_text="君才十倍曹丕，必能安国，终定大事。",
        white_text="刘备托孤诸葛亮，既表达高度信任，也用公开托付稳定继承结构。",
        text="刘备 诸葛亮 托孤 信任 授权 权责边界 公开承诺 稳定人心",
        people=["刘备", "诸葛亮", "刘禅"],
        events=["白帝托孤", "公开授权", "稳定权力结构"],
        topic_tags=["信任", "授权", "组织"],
        situation_tags=["君臣", "托付", "依赖"],
        source_priority=0.82,
    ),
]


def load_corpus(path: str | Path | None = None) -> list[HistoricalChunk]:
    configured_path = Path(os.getenv("ZIZHI_CORPUS_PATH")) if os.getenv("ZIZHI_CORPUS_PATH") else None
    if configured_path is not None:
        return _load_from_path(configured_path)

    if path is None:
        if DEFAULT_CACHE_PATH.exists() and DEFAULT_CACHE_PATH.stat().st_size > 0:
            try:
                chunks = load_chunks_jsonl(DEFAULT_CACHE_PATH)
                return chunks or SEED_CORPUS
            except Exception:
                pass
        return SEED_CORPUS

    return _load_from_path(Path(path))


def _load_from_path(path: Path) -> list[HistoricalChunk]:
    if not path.exists():
        return SEED_CORPUS

    if path.is_dir():
        return _load_or_build_txt_cache(path)

    if path.suffix.lower() == ".epub":
        return _load_or_build_epub_cache(path)

    chunks: list[HistoricalChunk] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if stripped:
                chunks.append(HistoricalChunk.model_validate(json.loads(stripped)))
    return chunks or SEED_CORPUS


def _load_or_build_epub_cache(epub_path: Path) -> list[HistoricalChunk]:
    cache_path = DEFAULT_CACHE_PATH
    if (
        cache_path.exists()
        and cache_path.stat().st_size > 0
        and cache_path.stat().st_mtime >= epub_path.stat().st_mtime
    ):
        try:
            chunks = load_chunks_jsonl(cache_path)
            return chunks or SEED_CORPUS
        except Exception:
            pass

    chunks = parse_epub_to_chunks(epub_path)
    if chunks:
        write_chunks_jsonl(chunks, cache_path)
        return chunks
    return SEED_CORPUS


def _load_or_build_txt_cache(corpus_root: Path) -> list[HistoricalChunk]:
    cache_path = DEFAULT_CACHE_PATH
    latest_txt_mtime = max((path.stat().st_mtime for path in corpus_root.rglob("*.txt")), default=0)
    if (
        cache_path.exists()
        and cache_path.stat().st_size > 0
        and cache_path.stat().st_mtime >= latest_txt_mtime
    ):
        try:
            chunks = load_chunks_jsonl(cache_path)
            return chunks or SEED_CORPUS
        except Exception:
            pass

    chunks = parse_txt_corpus_to_chunks(corpus_root)
    if chunks:
        write_txt_chunks_jsonl(chunks, cache_path)
        return chunks
    return SEED_CORPUS
