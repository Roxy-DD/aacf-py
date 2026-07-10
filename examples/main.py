# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 AACF Contributors
"""
main.py — AACF 内容创作助手演示 / AACF Content Creation Assistant Demo

展示五种核心能力 / Demonstrates five core capabilities:
  流式输出 / Streaming, 普通调用 / Regular call, 结构化 JSON / Structured JSON,
  显式代码覆盖 / Explicit code override, 智能路由 / Smart routing.
"""

import json
import sys

from agents import (
    app,
    article_writer,
    content_router,
    keyword_extractor,
    text_analyzer,
    title_generator,
)


def main():
    # ── 1. 流式输出：打字机效果 / Streaming output: typewriter effect ──
    print("【1. 流式输出 / Streaming】生成标题 / Generating titles...")
    for chunk in title_generator(topic="AI 改变日常生活"):
        print(chunk, end="", flush=True)
    print("\n")

    # ── 2. 普通调用 / Regular call ──
    print("【2. 普通调用 / Regular】撰写短文 / Writing article...")
    article = article_writer(title="当 AI 学会做饭：厨房里的智能革命")
    print(article)
    print()

    # ── 3. 结构化 JSON 输出 / Structured JSON output ──
    print("【3. 结构化 JSON / Structured JSON】提取关键词 / Extracting keywords...")
    result = keyword_extractor(text=article)
    try:
        print(json.dumps(json.loads(result), indent=2, ensure_ascii=False))
    except json.JSONDecodeError:
        print(f"原始输出 / Raw output: {result}")
    print()

    # ── 4. 显式代码覆盖 / Explicit code override ──
    print(
        "【4. 显式代码覆盖 / Code Override】使用自定义 prompt 覆盖默认生成器 / Using custom prompt to override default generator..."
    )
    print(text_analyzer(text=article))
    print()

    # ── 5. 智能路由：自动分发 / Smart routing: auto-dispatch ──
    print("【5. 智能路由 / Smart Routing】自动识别意图并分发 / Auto-detecting intent and dispatching...")
    print(content_router(user_req="帮我分析一下这段话的核心信息：量子计算正在突破传统算力瓶颈"))
    print()

    # ── 6. 管道执行 / Pipeline execution ──
    print("【6. 管道执行 / Pipeline】依赖分析与自动调度 / Dependency analysis and auto-scheduling...")

    # 查看依赖关系 / View dependencies
    dep_graph = app.get_dependency_graph()
    print(f"依赖图 / Dependency graph: {dep_graph}")

    exec_order = app.get_execution_order()
    print(f"执行顺序 / Execution order: {exec_order}")

    parallel_groups = app.get_parallel_groups()
    print(f"并行分组 / Parallel groups: {parallel_groups}")
    print()

    # 执行管道 / Execute pipeline
    print("执行管道 / Running pipeline...")
    results = app.run_pipeline(
        inputs={"extractor": {"raw_text": "量子计算正在突破传统算力瓶颈，未来可能改变整个计算行业"}}
    )

    print(f"\n提取结果 / Extractor result: {results.get('extractor', 'N/A')}")
    print(f"摘要结果 / Summarizer result: {results.get('summarizer', 'N/A')}")


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    main()
