# -*- coding: utf-8 -*-
"""测试集成后的混合检索流程：通过 historical_retriever() 调用"""
import os, sys
os.environ["ZIZHI_ENABLE_CASE_DENSE"] = "1"
sys.path.insert(0, ".")

from zizhi.case_retrieval import CaseRetriever
from zizhi.agents import llm_rerank_cases
from zizhi.schemas import AnalysisState, RetrievedCase

queries_list = [
    "老板的老婆不喜欢我，处处针对谣言我，该怎么办",
    "同村好友一起出来打工，但是他混的没有我好，他就开始处处的提防我，给我使绊子，我该怎么办",
]

retriever = CaseRetriever()

with open("test_results.txt", "w", encoding="utf-8") as f:
    for query in queries_list:
        f.write(f"{'='*60}\n")
        f.write(f"用户问题：{query}\n\n")

        # 模拟 historical_retriever 的流程
        coarse_k = int(os.getenv("ZIZHI_RERANK_CANDIDATES", "50"))
        coarse_results = retriever.search([query], top_k=coarse_k)

        f.write(f"--- 第一阶段：向量粗筛 top {coarse_k} (前10) ---\n")
        for i, c in enumerate(coarse_results[:10], 1):
            f.write(f"  [{i:2d}] [{c.retrieval_score:.4f}] {c.title}\n")

        # LLM 精选
        reranked = llm_rerank_cases(query, coarse_results, top_k=4)

        f.write(f"\n--- 第二阶段：LLM 精选 top 4 ---\n")
        for i, c in enumerate(reranked, 1):
            f.write(f"  [{i}] {c.title}\n")
            f.write(f"      分数: {c.retrieval_score}\n")
            f.write(f"      理由: {c.mapping_reason}\n")
        f.write("\n")

print("done")
