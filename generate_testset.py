# -*- coding: utf-8 -*-
"""生成检索测试集：从 case 库随机抽样，用 LLM 生成匿名化口语 query"""
import json, os, random, sys, time

sys.path.insert(0, ".")

CASE_PATH = ".cache/case_runs/case-corpus-through5033/case_profiles.jsonl"
OUTPUT_PATH = ".cache/testset_retrieval.jsonl"
SAMPLE_SIZE = 300
QUERIES_PER_CASE = 2

GENERATE_PROMPT = """你是一个测试数据生成专家。下面是一个历史案例的结构化信息，请根据它生成 {k} 条用户可能会怎么提问的口语化问题。

案例标题：{title}
核心冲突：{core_conflict}
可迁移模式：{pattern}
案例类型：{case_type}

要求：
1. 问题要模拟真实用户用口语描述自己的困境，像在向朋友倾诉或在网上求助
2. 不得出现任何历史人名、朝代名、典故名，全部用现代职场/生活场景改写
3. 保留案例的核心结构（谁对谁做了什么、困境是什么），但用现代语境表达
4. 每条问题要包含足够独特的细节，使得这个问题只能匹配这一个 pattern，不能泛泛而谈
5. 每条 15-40 字，风格自然，像真人说的话
6. {k} 条问题之间要有明显差异（不同角度、不同措辞）

输出格式：每行一条，不要编号，不要其他内容

示例：
案例标题：信任危机：刘邦如何应对下属对陈平的诋毁
好的问题：老板的亲信被人告发品行不端，老板决定先查清楚再处理
差的问题：有人在领导面前说我坏话（太泛，匹配太多案例）
"""


def main():
    # 加载 case 库
    with open(CASE_PATH, encoding="utf-8") as f:
        cases = [json.loads(line) for line in f if line.strip()]

    # 随机抽样
    random.seed(42)
    sampled = random.sample(cases, min(SAMPLE_SIZE, len(cases)))

    # 初始化 LLM
    from openai import OpenAI
    api_key = os.getenv("DEEPSEEK_API_KEY")
    base_url = os.getenv("ZIZHI_ROUTER_BASE_URL", "https://api.deepseek.com").strip()
    model = os.getenv("ZIZHI_ROUTER_MODEL", "deepseek-chat").strip() or "deepseek-chat"
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=30)

    # 生成测试集
    results = []
    errors = 0
    for i, case in enumerate(sampled):
        title = case.get("title", "")
        core_conflict = case.get("core_conflict", "")
        pattern = case.get("transferable_pattern", "")
        case_type = case.get("case_type", "mixed")

        if not pattern:
            continue

        prompt = GENERATE_PROMPT.format(
            k=QUERIES_PER_CASE,
            title=title,
            core_conflict=core_conflict,
            pattern=pattern,
            case_type=case_type,
        )

        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
            )
            content = (response.choices[0].message.content or "").strip()
            queries = [q.strip() for q in content.split("\n") if q.strip() and len(q.strip()) >= 8]

            for q in queries[:QUERIES_PER_CASE]:
                results.append({
                    "query": q,
                    "expected_case_id": case.get("case_id", ""),
                    "expected_title": title,
                    "expected_pattern": pattern,
                    "case_type": case_type,
                })
        except Exception as e:
            errors += 1

        # 进度
        if (i + 1) % 50 == 0:
            print(f"  [{i+1}/{len(sampled)}] generated {len(results)} queries, {errors} errors")

        # 限速
        time.sleep(0.1)

    # 保存
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\nDone: {len(results)} test samples from {len(sampled)} cases → {OUTPUT_PATH}")
    print(f"Errors: {errors}")


if __name__ == "__main__":
    main()
