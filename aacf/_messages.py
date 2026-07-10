# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 AACF Contributors
"""
AACF Messages — Bilingual prompt templates and docstring formats / 双语提示词模板与文档格式

This module centralizes all user-facing text templates for internationalization.
本模块集中管理所有面向用户的文本模板，用于国际化支持。

Currently supports: Chinese (zh) and English (en)
当前支持：中文 (zh) 和英文 (en)

Sections / 模块结构:
    PROMPT_TEMPLATES:   Templates for @app.node() prompt construction / 节点 prompt 构建模板
    DOCSTRING_TEMPLATES: Templates for docstring injection / Docstring 注入模板
    CLI_MESSAGES:        Templates for CLI output messages / CLI 输出消息模板
    get_template():      Helper function to retrieve templates by lang/category/key / 模板获取辅助函数
"""

# ────────────────────────────────────────────────────────────
# Prompt Templates for @app.node() / @app.node() 提示词模板
# ────────────────────────────────────────────────────────────

PROMPT_TEMPLATES = {
    "zh": {
        "role": "你是{who}，你在{where}，你是一个{what}。\n",
        "intent": "操作的意图原因是：{why}。\n",
        "how": "你有以下操作选项：{how}\n",
        "routing_header": "\n【重要：智能路由分发模式】\n",
        "routing_modules": "你有权调用的下级专业子模块/节点有：{modules}\n",
        "routing_instruction": "请深入分析用户的意图，自主判断应该去调用上述哪个子节点来完成任务。\n",
        "routing_format": "你只需要输出一个纯 JSON 对象，格式为：\n",
        "routing_example": '{"target_node": "节点名称", "reason": "调用原因", "inputs": {"参数名": "参数值"}}\n',
        "routing_fallback": "如果你认为不需要调用任何子模块，请直接完成用户的需求。\n\n",
        "output_request": "请根据输入内容，按照输出要求生成内容。\n",
        "output_requirement": "输出要求：{out}\n",
    },
    "en": {
        "role": "You are {who}, working in {where}, and your role is {what}.\n",
        "intent": "The intent behind this operation is: {why}.\n",
        "how": "You have the following operational options: {how}\n",
        "routing_header": "\n[IMPORTANT: Intelligent Routing Mode]\n",
        "routing_modules": "You have access to the following specialized sub-modules/nodes: {modules}\n",
        "routing_instruction": "Please analyze the user's intent deeply and autonomously determine which sub-node to invoke.\n",
        "routing_format": "Output only a pure JSON object in this format:\n",
        "routing_example": '{"target_node": "node_name", "reason": "reason_for_call", "inputs": {"param_name": "param_value"}}\n',
        "routing_fallback": "If you determine no sub-module is needed, please fulfill the user's request directly.\n\n",
        "output_request": "Please generate content based on the input according to the output requirements.\n",
        "output_requirement": "Output requirements: {out}\n",
    },
}


# ────────────────────────────────────────────────────────────
# Docstring Injection Templates / Docstring 注入模板
# ────────────────────────────────────────────────────────────

DOCSTRING_TEMPLATES = {
    "zh": {
        "header": "🤖 【AACF 智能节点】: {who}\n",
        "task": " 核心任务: {what}\n",
        "env": "📍 执行环境: {where}\n",
    },
    "en": {
        "header": "🤖 [AACF Smart Node]: {who}\n",
        "task": "🎯 Core Task: {what}\n",
        "env": "📍 Environment: {where}\n",
    },
}


# ────────────────────────────────────────────────────────────
# CLI Messages / CLI 输出消息
# ────────────────────────────────────────────────────────────

CLI_MESSAGES = {
    "zh": {
        "init_start": "正在初始化 AACF 项目：",
        "init_creating": "正在创建项目结构...",
        "init_done": "✔ 项目结构已创建。",
        "init_venv": "✔ 虚拟环境已初始化。",
        "init_next": "下一步：",
        "run_start": "▶ 正在运行 AACF 脚本：",
        "run_error": "✖ 脚本退出，错误码：",
        "sync_scanning": "▶ 正在扫描 @app.node：",
        "sync_injecting": "正在注入 docstring...",
        "sync_success": "✔ 成功为 {count} 个文件注入 docstring。",
        "sync_hint": "你的 IDE（如 Pylance）现在将显示完整的 docstring 和类型提示。",
        "sync_none": "ℹ 未找到需要同步的 @app.node 函数。",
        "doc_start": "▶ 正在启动 AACF 文档服务器：",
        "doc_serving": "服务地址：http://localhost:{port}",
        "doc_stop": "按 Ctrl+C 停止。",
        "doc_missing": "✖ pdoc 未安装。请运行 `pip install pdoc`。",
        "doc_stopped": "✔ 文档服务器已停止。",
        "doc_error": "✖ 启动文档服务器时出错：",
        "watch_start": "▶ 正在监听文件变化：",
        "watch_stop": "按 Ctrl+C 停止。",
        "watch_changes": "检测到 {count} 个文件变化，正在同步...",
        "watch_injected": "✔ 已为 {count} 个文件注入 docstring。",
        "watch_noop": "无需更新 @app.node。",
        "watch_stopped": "✔ 监听器已停止。",
    },
    "en": {
        "init_start": "Initializing AACF Project: ",
        "init_creating": "Creating project structure...",
        "init_done": "✔ Project structure created.",
        "init_venv": "✔ Virtual environment initialized.",
        "init_next": "Next steps:",
        "run_start": "▶ Running AACF Script: ",
        "run_error": "✖ Script exited with error code: ",
        "sync_scanning": "▶ Scanning for @app.node in: ",
        "sync_injecting": "Injecting docstrings...",
        "sync_success": "✔ Successfully injected docstrings for {count} files.",
        "sync_hint": "Your IDE (e.g., Pylance) will now show perfect docstrings and type hints.",
        "sync_none": " No @app.node functions found to sync.",
        "doc_start": "▶ Starting AACF Doc Server for: ",
        "doc_serving": "Serving on http://localhost:{port}",
        "doc_stop": "Press Ctrl+C to stop.",
        "doc_missing": "✖ pdoc is not installed. Please run `pip install pdoc`.",
        "doc_stopped": "✔ Doc server stopped.",
        "doc_error": "✖ Error starting doc server: ",
        "watch_start": "▶ Watching for changes in: ",
        "watch_stop": "Press Ctrl+C to stop.",
        "watch_changes": "Changes detected in {count} file(s). Syncing...",
        "watch_injected": "✔ Injected docstrings for {count} file(s).",
        "watch_noop": "No @app.node updates required.",
        "watch_stopped": "✔ Watcher stopped.",
    },
}


# ────────────────────────────────────────────────────────────
# Helper Functions / 辅助函数
# ────────────────────────────────────────────────────────────


def get_template(lang: str, category: str, key: str) -> str:
    """
    Get a template string by language, category, and key.

    Args:
        lang: Language code ("zh" or "en")
        category: Template category ("prompt", "docstring", "cli")
        key: Template key within the category

    Returns:
        Template string, falling back to Chinese if language not found
    """
    templates = {
        "prompt": PROMPT_TEMPLATES,
        "docstring": DOCSTRING_TEMPLATES,
        "cli": CLI_MESSAGES,
    }

    category_dict = templates.get(category, {})
    lang_dict = category_dict.get(lang, category_dict.get("zh", {}))
    return lang_dict.get(key, "")
