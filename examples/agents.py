# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 AACF Contributors
"""
agents.py — 内容创作助手 / Content Creation Assistant

演示 AACF 的核心用法 / Demonstrates core AACF features:
  1. 流式输出 / Streaming output (stream)
  2. 结构化 JSON 输出 / Structured JSON output (format="json")
  3. 显式代码覆盖 / Explicit code override (manual prompt overrides default generator)
  4. 智能路由分发 / Smart routing dispatch (module)
"""
from aacf import AACF, LLMConfig

# ── 初始化应用 / Initialize App ──────────────────────────────────────
# 默认使用中文 prompt / Default to Chinese prompts
app = AACF(__name__, config=LLMConfig(
    model="qwen2.5-7b-instruct",
    url="http://127.0.0.1:8080/v1/chat/completions",
    language="zh",  # 可选值 / Options: "zh" (中文), "en" (English)
))


# ── 节点定义 ────────────────────────────────────────

@app.node(
    who="标题创意师",
    what="为给定主题生成 3 个富有吸引力的文章标题",
    stream=True,
)
def title_generator(topic: str):
    """
     【AACF 智能节点 / Smart Node】: 标题创意师
    🎯 核心任务 / Core Task: 为给定主题生成 3 个富有吸引力的文章标题
     执行环境 / Environment: 
    """
    pass


@app.node(
    who="专栏作家",
    what="根据给定标题撰写一篇 200 字左右的短文",
    where="科技媒体专栏",
)
def article_writer(title: str):
    """
     【AACF 智能节点 / Smart Node】: 专栏作家
    🎯 核心任务 / Core Task: 根据给定标题撰写一篇 200 字左右的短文
     执行环境 / Environment: 科技媒体专栏
    """
    pass


@app.node(
    who="内容分析师",
    what="从文本中提取关键词并评估其所属领域",
    format="json",
    out='{"keywords": ["关键词1", ...], "domain": "领域", "summary": "一句话摘要"}',
)
def keyword_extractor(text: str):
    """
     【AACF 智能节点 / Smart Node】: 内容分析师
    🎯 核心任务 / Core Task: 从文本中提取关键词并评估其所属领域
     执行环境 / Environment: 
    """
    pass


@app.node(who="文本分析师", what="分析文本特征")
def text_analyzer(text: str):
    """
    显式代码覆盖：函数体有实际代码时，覆盖默认的 prompt 生成逻辑。
    装饰器配置（who, what）保留，但不会使用。
    改回 pass 即可恢复默认行为。
    """
    from aacf.core import llm_call
    # 手动构建自定义 prompt，覆盖默认生成器
    custom_prompt = f"""请分析以下文本的特征：

文本内容：{text}

请从以下维度分析：
1. 文本类型（叙述/议论/说明等）
2. 情感倾向（正面/负面/中性）
3. 关键主题词

输出格式：JSON"""
    
    return llm_call(
        system_prompt=custom_prompt,
        user_prompt=text,
        temperature=0.3,  # 自定义参数
    )


@app.node(
    who="内容总监",
    what="分析用户需求，分派给最合适的专业节点处理",
    module=[title_generator, article_writer, keyword_extractor],
)
def content_router(user_req: str):
    """
     【AACF 智能节点 / Smart Node】: 内容总监
    🎯 核心任务 / Core Task: 分析用户需求，分派给最合适的专业节点处理
     执行环境 / Environment: 
    """
    pass


# ── 管道执行示例节点 / Pipeline execution example nodes ──
# 这些节点演示依赖关系和管道执行 / These nodes demonstrate dependencies and pipeline execution

@app.node(
    who="文本提取器",
    what="从原始文本中提取关键信息",
    cache_enabled=True,   # 启用缓存 / Enable caching
    cache_ttl=300,        # 缓存 5 分钟 / Cache for 5 minutes
    max_retries=2,        # 失败重试 2 次 / Retry 2 times on failure
)
def extractor(raw_text: str):
    """
     【AACF 智能节点 / Smart Node】: 文本提取器
    🎯 核心任务 / Core Task: 从原始文本中提取关键信息
     执行环境 / Environment: 
    """
    pass


@app.node(
    who="摘要生成器",
    what="根据提取的信息生成摘要",
    cache_enabled=True,   # 启用缓存 / Enable caching
)
def summarizer(extractor: str):
    """
     【AACF 智能节点 / Smart Node】: 摘要生成器
    🎯 核心任务 / Core Task: 根据提取的信息生成摘要
     执行环境 / Environment: 
    """
    # 参数名 extractor 匹配上游节点名，自动建立依赖关系
    # Parameter name 'extractor' matches upstream node name, automatically establishes dependency
    pass
