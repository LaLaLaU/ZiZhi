# -*- coding: utf-8 -*-
"""检索评估脚本：跑测试集，计算 Recall@K / MRR / Hit Rate"""
import json, os, sys, time

os.environ["ZIZHI_ENABLE_CASE_DENSE"] = "1"
sys.path.insert(0, ".")

from zizhi.case_retrieval import CaseRetriever

TESTSET_PATH = ".cache/testset_retrieval.jsonl"
TOP_K = 4


def load_testset(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def evaluate(retriever: CaseRetriever, testset: list[dict], use_rerank: bool = False) -> dict:
    """评估检索效果，返回指标和详细结果。"""
    if use_rerank:
        from zizhi.agents import llm_rerank_cases
        coarse_k = int(os.getenv("ZIZHI_RERANK_CANDIDATES", "50"))

    hits = 0
    mrr_sum = 0.0
    details = []
    by_type = {}  # case_type -> {total, hit, mrr_sum}

    for i, entry in enumerate(testset):
        query = entry["query"]
        expected_id = entry["expected_case_id"]
        case_type = entry.get("case_type", "mixed")

        # 检索
        if use_rerank:
            coarse = retriever.search([query], top_k=coarse_k)
            results = llm_rerank_cases(query, coarse, top_k=TOP_K)
        else:
            results = retriever.search([query], top_k=TOP_K)

        # 检查是否命中
        result_ids = [c.case_id for c in results]
        rank = -1
        for j, cid in enumerate(result_ids):
            if cid == expected_id:
                rank = j + 1
                break

        hit = rank > 0
        reciprocal_rank = 1.0 / rank if hit else 0.0

        if hit:
            hits += 1
        mrr_sum += reciprocal_rank

        # 按类型统计
        if case_type not in by_type:
            by_type[case_type] = {"total": 0, "hit": 0, "mrr_sum": 0.0}
        by_type[case_type]["total"] += 1
        if hit:
            by_type[case_type]["hit"] += 1
        by_type[case_type]["mrr_sum"] += reciprocal_rank

        details.append({
            "query": query,
            "expected_id": expected_id,
            "expected_title": entry.get("expected_title", ""),
            "case_type": case_type,
            "hit": hit,
            "rank": rank,
            "reciprocal_rank": round(reciprocal_rank, 4),
            "top_results": [{"id": c.case_id, "title": c.title} for c in results[:TOP_K]],
        })

        if (i + 1) % 50 == 0:
            print(f"  [{i+1}/{len(testset)}] hit_rate={hits/(i+1):.1%} mrr={mrr_sum/(i+1):.3f}")

    n = len(testset)
    metrics = {
        "total": n,
        "hit_count": hits,
        "hit_rate": round(hits / n, 4) if n else 0,
        "mrr": round(mrr_sum / n, 4) if n else 0,
        "by_type": {},
    }
    for t, v in by_type.items():
        metrics["by_type"][t] = {
            "total": v["total"],
            "hit_rate": round(v["hit"] / v["total"], 4) if v["total"] else 0,
            "mrr": round(v["mrr_sum"] / v["total"], 4) if v["total"] else 0,
        }

    return {"metrics": metrics, "details": details}


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "baseline"  # baseline | rerank
    use_rerank = mode == "rerank"

    testset = load_testset(TESTSET_PATH)
    print(f"Loaded {len(testset)} test samples")
    print(f"Mode: {mode}")

    retriever = CaseRetriever()
    t0 = time.time()
    result = evaluate(retriever, testset, use_rerank=use_rerank)
    elapsed = time.time() - t0

    # 输出报告
    m = result["metrics"]
    report_path = f".cache/eval_{mode}_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"Mode: {mode} | Time: {elapsed:.1f}s")
    print(f"{'='*50}")
    print(f"Hit Rate: {m['hit_rate']:.1%} ({m['hit_count']}/{m['total']})")
    print(f"MRR:      {m['mrr']:.4f}")
    print(f"\nBy case_type:")
    for t, v in sorted(m["by_type"].items()):
        print(f"  {t:15s}  hit={v['hit_rate']:.1%}  mrr={v['mrr']:.4f}  n={v['total']}")
    print(f"\nReport: {report_path}")

    # 输出 miss 列表（用于第二层 LLM 裁判）
    misses = [d for d in result["details"] if not d["hit"]]
    miss_path = f".cache/eval_{mode}_misses.jsonl"
    with open(miss_path, "w", encoding="utf-8") as f:
        for m in misses:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
    print(f"Misses: {len(misses)} → {miss_path}")


if __name__ == "__main__":
    main()
