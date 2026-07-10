# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 AACF Contributors
"""
AACF Core — Agentic AI Compiler Framework / AACF 核心引擎

This is the sole runtime engine for AACF, containing:
- LLMConfig: LLM call configuration / 大模型调用配置
- llm_call: OpenAI-compatible HTTP call with exponential backoff retry / OpenAI 兼容的 HTTP 调用（带指数退避重试）
- AACF: Flask-style app registry and @app.node() decorator / Flask 风格的应用注册表与 @app.node() 装饰器
"""

import ast
import atexit
import copy
import inspect
import json
import logging
import sys
import textwrap
import time
import typing
import urllib.error
import urllib.request
from functools import wraps
from typing import Any, Dict, List, Optional, Set

if sys.version_info >= (3, 12):
    from typing import TypedDict, Unpack
else:
    from typing_extensions import TypedDict, Unpack

from typing import ParamSpec

P = ParamSpec("P")

from aacf._messages import PROMPT_TEMPLATES
from aacf.compiler import (
    AtomicNodeConfig,
    AtomicScheduler,
    DependencyAnalyzer,
    ExecutionPlanner,
    NodeStatus,
)

logger = logging.getLogger("aacf")


# ─────────────────────────────────────────────
# NodeBuilder — 链式调用构建器 / Fluent builder
# ─────────────────────────────────────────────


class NodeBuilder:
    """
    链式调用节点构建器 / Fluent node builder with chainable API.

    提供可发现的配置方式，支持 IDE 自动补全。
    Provides discoverable configuration with IDE auto-completion support.

    Usage::

        app = AACF(__name__)

        # 链式调用 / Chainable API
        @app.node("translator")
        def translator(text: str):
            pass

        translator = (
            app.node("translator")
            .who("翻译员")
            .what("将文本翻译为英文")
            .where("国际化团队")
            .cache(ttl=300)
            .retry(max_attempts=3, delay=1.0)
            .build()
        )
    """

    def __init__(self, app: "AACF", name: str, func: Optional[typing.Callable] = None):
        """
        初始化节点构建器 / Initialize node builder.

        Args:
            app: AACF 应用实例 / AACF app instance
            name: 节点名称 / Node name
            func: 可选的函数对象 / Optional function object
        """
        self._app = app
        self._name = name
        self._func = func

        # DSL 元数据 / DSL metadata
        self._who = ""
        self._where = ""
        self._what = ""
        self._why = ""
        self._how = ""
        self._module = ""
        self._out = ""
        self._stream = False
        self._format = ""
        self._branches = None

        # 执行配置 / Execution config
        self._cache_enabled = False
        self._cache_ttl = 0
        self._max_retries = 3
        self._retry_delay = 1.0
        self._timeout = 0

    # ── DSL 元数据方法 / DSL metadata methods ──

    def who(self, role: str) -> "NodeBuilder":
        """
        设置智能体角色 / Set agent role.

        Args:
            role: 角色描述 / Role description

        Returns:
            self（支持链式调用）/ self (for chaining)
        """
        self._who = role
        return self

    def where(self, context: str) -> "NodeBuilder":
        """
        设置业务环境 / Set business context.

        Args:
            context: 环境描述 / Context description

        Returns:
            self（支持链式调用）/ self (for chaining)
        """
        self._where = context
        return self

    def what(self, task: str) -> "NodeBuilder":
        """
        设置核心任务 / Set core task.

        Args:
            task: 任务描述 / Task description

        Returns:
            self（支持链式调用）/ self (for chaining)
        """
        self._what = task
        return self

    def why(self, reason: str) -> "NodeBuilder":
        """
        设置执行意图 / Set execution intent.

        Args:
            reason: 原因描述 / Reason description

        Returns:
            self（支持链式调用）/ self (for chaining)
        """
        self._why = reason
        return self

    def how(self, method: typing.Union[str, typing.List[str]]) -> "NodeBuilder":
        """
        设置操作方法 / Set operation method.

        Args:
            method: 方法描述或步骤列表 / Method description or step list

        Returns:
            self（支持链式调用）/ self (for chaining)
        """
        self._how = method
        return self

    def module(self, nodes: typing.Union[str, typing.List[typing.Callable]]) -> "NodeBuilder":
        """
        设置智能路由模块 / Set smart routing modules.

        Args:
            nodes: 下级节点函数列表 / Sub-node function list

        Returns:
            self（支持链式调用）/ self (for chaining)
        """
        self._module = nodes
        return self

    def out(self, format_req: str) -> "NodeBuilder":
        """
        设置输出格式要求 / Set output format requirement.

        Args:
            format_req: 格式描述 / Format description

        Returns:
            self（支持链式调用）/ self (for chaining)
        """
        self._out = format_req
        return self

    def stream(self, enabled: bool = True) -> "NodeBuilder":
        """
        启用流式输出 / Enable streaming output.

        Args:
            enabled: 是否启用 / Whether to enable (default: True)

        Returns:
            self（支持链式调用）/ self (for chaining)
        """
        self._stream = enabled
        return self

    def format(self, fmt: str) -> "NodeBuilder":
        """
        设置输出格式 / Set output format.

        Args:
            fmt: 格式类型（如 "json"）/ Format type (e.g., "json")

        Returns:
            self（支持链式调用）/ self (for chaining)
        """
        self._format = fmt
        return self

    def branches(self, mapping: Dict[str, typing.Callable]) -> "NodeBuilder":
        """
        设置条件分支 / Set conditional branches.

        Args:
            mapping: 条件键到分支函数的映射 / Mapping of condition keys to branch functions

        Returns:
            self（支持链式调用）/ self (for chaining)
        """
        self._branches = mapping
        return self

    # ── 执行配置方法 / Execution config methods ──

    def cache(self, enabled: bool = True, ttl: int = 0) -> "NodeBuilder":
        """
        配置缓存 / Configure caching.

        Args:
            enabled: 是否启用缓存 / Whether to enable cache (default: True)
            ttl: 缓存有效期（秒），0 表示永不过期 / Cache TTL in seconds, 0 = no expiry (default: 0)

        Returns:
            self（支持链式调用）/ self (for chaining)
        """
        self._cache_enabled = enabled
        self._cache_ttl = ttl
        return self

    def retry(self, max_attempts: int = 3, delay: float = 1.0) -> "NodeBuilder":
        """
        配置重试策略 / Configure retry strategy.

        Args:
            max_attempts: 最大重试次数 / Maximum retry attempts (default: 3)
            delay: 重试间隔（秒）/ Retry delay in seconds (default: 1.0)

        Returns:
            self（支持链式调用）/ self (for chaining)
        """
        self._max_retries = max_attempts
        self._retry_delay = delay
        return self

    def timeout(self, seconds: int) -> "NodeBuilder":
        """
        设置执行超时 / Set execution timeout.

        Args:
            seconds: 超时时间（秒），0 表示无超时 / Timeout in seconds, 0 = no timeout

        Returns:
            self（支持链式调用）/ self (for chaining)
        """
        self._timeout = seconds
        return self

    # ── 构建方法 / Build methods ──

    def build(self) -> typing.Callable:
        """
        构建节点装饰器 / Build node decorator.

        如果函数已绑定（通过 __call__），返回装饰后的函数。
        如果函数未绑定，返回一个装饰器，可用于 @ 语法。

        If function is bound (via __call__), returns the decorated function.
        If function is not bound, returns a decorator for @ syntax.

        Returns:
            装饰器函数或装饰后的函数 / Decorator function or decorated function
        """
        decorator = self._app._create_node_decorator(
            who=self._who,
            where=self._where,
            what=self._what,
            why=self._why,
            how=self._how,
            module=self._module,
            out=self._out,
            stream=self._stream,
            format=self._format,
            cache_enabled=self._cache_enabled,
            cache_ttl=self._cache_ttl,
            max_retries=self._max_retries,
            retry_delay=self._retry_delay,
            timeout=self._timeout,
            branches=self._branches,
        )

        if self._func is not None:
            return decorator(self._func)

        # Return decorator for @ syntax / 返回装饰器用于 @ 语法
        return decorator

    def __call__(self, func: typing.Callable) -> typing.Callable:
        """
        作为装饰器使用（仅用于 @app.node("name") 无配置场景）/ Use as decorator (only for @app.node("name") without configuration).

        Args:
            func: 被装饰的函数 / Function to decorate

        Returns:
            装饰后的函数 / Decorated function
        """
        self._func = func
        return self.build()


# ─────────────────────────────────────────────
# LLMConfig — 大模型配置 / LLM Configuration
# ─────────────────────────────────────────────


class LLMConfigKwargs(TypedDict, total=False):
    """
    LLM 配置参数字典 / LLM configuration parameter dictionary.

    All fields are optional. Fields not specified will use default values.
    所有字段均为可选，未指定的字段将使用默认值。

    Attributes:
        model: 模型名称 / Model name (default: "qwen2.5-7b-instruct")
        temperature: 采样温度 / Sampling temperature (default: 0.7)
        max_tokens: 最大输出 token 数 / Max output tokens (default: 1024)
        stream: 是否流式输出 / Enable streaming output (default: False)
        json_mode: 是否强制 JSON 输出 / Force JSON output format (default: False)
        url: API 端点地址 / API endpoint URL (default: "http://127.0.0.1:8080/v1/chat/completions")
        api_key: API 密钥（本地模型可省略）/ API key (optional for local models)
        language: Prompt 语言 / Prompt language, "zh" or "en" (default: "zh")
    """

    model: str
    temperature: float
    max_tokens: int
    stream: bool
    json_mode: bool
    url: str
    api_key: str
    language: str


class LLMConfig:
    """
    LLM call configuration class / 大语言模型调用配置类。

    Supports safe property override via `__call__` to create derived config copies.
    IDE uses Unpack[TypedDict] for optimal code completion.
    支持安全覆盖属性，创建派生配置副本。IDE 利用 Unpack[TypedDict] 提供极致的代码补全。

    Usage::

        base = LLMConfig(model="qwen2.5-7b", url="http://localhost:8080/v1/chat/completions")
        streaming = base(stream=True)   # Derive a new config with streaming enabled / 派生一个开启流式的新配置
    """

    def __init__(self, **kwargs: Unpack[LLMConfigKwargs]):
        """
        初始化 LLM 配置 / Initialize LLM configuration.

        Args:
            **kwargs: 配置参数，参见 LLMConfigKwargs / Config params, see LLMConfigKwargs
        """
        self.config: Dict[str, Any] = kwargs or {}

    def __call__(self, **kwargs: Unpack[LLMConfigKwargs]) -> "LLMConfig":
        """
        创建派生配置副本，安全覆盖指定属性 / Create a derived config copy with safe property override.

        原配置不受影响，返回新的 LLMConfig 实例。
        Original config is not modified; returns a new LLMConfig instance.

        Args:
            **kwargs: 要覆盖的配置参数 / Config params to override

        Returns:
            新的 LLMConfig 实例 / New LLMConfig instance
        """
        new_config = copy.deepcopy(self.config)
        new_config.update(kwargs)
        return LLMConfig(**new_config)

    def get_dict(self) -> Dict[str, Any]:
        """
        获取配置字典 / Get the configuration dictionary.

        Returns:
            当前配置参数字典 / Current config parameter dictionary
        """
        return self.config

    def get_language(self) -> str:
        """Get the configured language, defaults to 'zh' / 获取配置的语言，默认为 'zh'"""
        return self.config.get("language", "zh") if self.config else "zh"


# ─────────────────────────────────────────────
# llm_call — OpenAI 兼容 HTTP 调用 / OpenAI-compatible HTTP call
# ─────────────────────────────────────────────


def _is_function_body_pass(func) -> bool:
    """
    检查函数体是否只有 pass 语句。

    用于判断是否使用默认的 LLM 调用逻辑：
    - 函数体为 pass → 使用装饰器配置自动生成 prompt 并调用 LLM
    - 函数体有实际代码 → 执行用户自定义代码（显式覆盖）

    Args:
        func: 要检查的函数对象

    Returns:
        True 表示函数体只有 pass，False 表示有实际代码
    """
    try:
        source = inspect.getsource(func)
        # 去除公共缩进，避免在类方法中定义时解析失败
        # Remove common leading whitespace to avoid parse failures in nested contexts
        source = textwrap.dedent(source)
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func.__name__:
                body = node.body

                if len(body) == 1 and isinstance(body[0], ast.Pass):
                    return True

                if len(body) == 2:
                    if isinstance(body[0], ast.Expr) and isinstance(body[0].value, (ast.Str, ast.Constant)):
                        if isinstance(body[1], ast.Pass):
                            return True

                return False

        return True
    except (OSError, TypeError):
        return True


def llm_call(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    stream: bool = False,
    json_mode: bool = False,
    llm_config=None,
) -> typing.Union[str, typing.Generator[str, None, None]]:
    """
    向 OpenAI 兼容的 LLM API 发送 HTTP 请求 / Send HTTP request to OpenAI-compatible LLM API.

    支持流式输出（SSE）和非流式输出，带指数退避重试机制（最多 3 次）。
    Supports streaming (SSE) and non-streaming output, with exponential backoff retry (max 3 attempts).

    当函数体有实际代码时（显式代码覆盖），用户可直接调用此函数，
    手动构建 prompt 并自定义参数，覆盖 @app.node() 的默认生成逻辑。
    When function body has actual code (explicit override), users can call this directly
    to manually build prompts and customize parameters, overriding @app.node() defaults.

    Args:
        system_prompt: 系统提示词 / System prompt
        user_prompt: 用户输入内容 / User input content
        temperature: 采样温度，0-2 之间 / Sampling temperature, between 0-2
        stream: 是否流式输出 / Enable streaming output
        json_mode: 是否强制 JSON 输出 / Force JSON output format
        llm_config: LLM 配置对象或字典 / LLM config object or dict

    Returns:
        非流式时返回 str，流式时返回 Generator[str, None, None]
        Returns str for non-streaming, Generator[str, None, None] for streaming
    """
    config = {}

    if llm_config is not None:
        if hasattr(llm_config, "get_dict"):
            config.update(llm_config.get_dict())
        elif isinstance(llm_config, dict):
            config.update(llm_config)

    url = config.get("url", "http://127.0.0.1:8080/v1/chat/completions")
    model = config.get("model", "qwen2.5-7b-instruct")
    api_key = config.get("api_key", "")
    max_tokens = config.get("max_tokens", 1024)
    temperature = config.get("temperature", temperature)
    stream = config.get("stream", stream)
    json_mode = config.get("json_mode", json_mode)

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        data["response_format"] = {"type": "json_object"}
    if stream:
        data["stream"] = True

    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = urllib.request.urlopen(req, timeout=120)

            if stream:

                def event_generator():
                    with response:
                        for line in response:
                            line = line.decode("utf-8").strip()
                            if line.startswith("data: "):
                                payload = line[6:]
                                if payload == "[DONE]":
                                    break
                                try:
                                    chunk = json.loads(payload)
                                    content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                    if content:
                                        yield content
                                except Exception:
                                    pass

                return event_generator()
            else:
                with response:
                    result = json.loads(response.read().decode("utf-8"))
                    try:
                        return result["choices"][0]["message"]["content"].strip()
                    except (KeyError, IndexError):
                        logger.error(f"Unrecognized response format: {result}")
                        return f"[LLM Client Error]: Unrecognized response format - {result}"

        except urllib.error.URLError as e:
            wait_time = 2**attempt
            logger.warning(
                f"Local LLM API request failed (Attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s..."
            )
            time.sleep(wait_time)
        except Exception as e:
            logger.error(f"Unexpected error during API call: {e}")
            if stream:
                return (msg for msg in [f"[LLM Client Error]: {e}"])
            return f"[LLM Client Error]: {e}"

    logger.error("All retries failed. Returning mock result.")
    if stream:
        return (msg for msg in [f"[Mock Result for: {user_prompt[:20]}...]"])
    return f"[Mock Result for: {user_prompt[:20]}...]"


# ─────────────────────────────────────────────
# Docstring 自动注入（atexit hook）/ Auto-inject docstrings on exit
# ─────────────────────────────────────────────

_AACF_NODE_REGISTRY: Dict[str, list] = {}
_AACF_ATEXIT_REGISTERED = False


def _inject_docstrings_on_exit():
    """
    脚本退出时自动向源文件注入 Docstring / Auto-inject docstrings into source files on script exit.

    通过 atexit 钩子触发，扫描所有注册的 @app.node 函数，
    将装饰器元数据（who, what, where）格式化为双语 docstring 并写入源码。
    Triggered via atexit hook, scans all registered @app.node functions,
    formats decorator metadata (who, what, where) into bilingual docstrings and writes to source.
    """
    if not _AACF_NODE_REGISTRY:
        return

    def _inject_docstrings_to_py(filepath, nodes):
        """
        将 docstring 注入到单个 Python 文件中 / Inject docstrings into a single Python file.

        Args:
            filepath: 目标文件路径 / Target file path
            nodes: (函数对象, 元数据字典, 签名) 的列表 / List of (func, meta_dict, signature) tuples
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                source_lines = f.readlines()
            tree = ast.parse("".join(source_lines))
            docstring_ranges = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    doc = ast.get_docstring(node)
                    if doc and "AACF" in doc:
                        expr_node = node.body[0]
                        docstring_ranges[node.name] = (expr_node.lineno, expr_node.end_lineno)
        except Exception:
            return

        funcs_to_inject = []
        for func, meta, sig in nodes:
            doc = getattr(func, "__doc__", None)
            if doc and "AACF" not in doc:
                continue
            try:
                _, start_lineno = inspect.getsourcelines(func)
            except Exception:
                continue
            funcs_to_inject.append((start_lineno, func, meta))

        if not funcs_to_inject:
            return

        funcs_to_inject.sort(key=lambda x: x[0], reverse=True)

        for start_lineno, func, meta in funcs_to_inject:
            name = func.__name__
            if name in docstring_ranges:
                start, end = docstring_ranges[name]
                del source_lines[start - 1 : end]

            idx = start_lineno - 1
            paren_count = 0
            in_def = False
            colon_idx = idx
            def_indent = 0
            for i in range(idx, len(source_lines)):
                line = source_lines[i]
                if not in_def and line.lstrip().startswith("def "):
                    in_def = True
                    def_indent = len(line) - len(line.lstrip())
                paren_count += line.count("(") - line.count(")")
                if in_def and paren_count == 0 and ":" in line:
                    colon_idx = i
                    break

            indent_str = " " * (def_indent + 4)
            who = meta.get("who", "未命名智能体 / AI Agent")
            what = meta.get("what", "未定义任务 / Task undefined")
            where = meta.get("where", "未知环境 / Environment unknown")

            docstring_lines = [
                f'{indent_str}"""\n',
                f"{indent_str} 【AACF 智能节点 / Smart Node】: {who}\n",
                f"{indent_str}🎯 核心任务 / Core Task: {what}\n",
                f"{indent_str} 执行环境 / Environment: {where}\n",
                f'{indent_str}"""\n',
            ]

            line = source_lines[colon_idx]
            colon_pos = line.find(":", line.rfind(")"))
            if colon_pos != -1:
                before_colon = line[: colon_pos + 1]
                after_colon = line[colon_pos + 1 :].strip()
                source_lines[colon_idx] = before_colon + "\n"
                if after_colon:
                    docstring_lines.append(f"{indent_str}{after_colon}\n")

            source_lines = source_lines[: colon_idx + 1] + docstring_lines + source_lines[colon_idx + 1 :]

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.writelines(source_lines)
        except Exception as e:
            print(f"Failed to write injected file {filepath}: {e}")

    for filepath, nodes in _AACF_NODE_REGISTRY.items():
        _inject_docstrings_to_py(filepath, nodes)


# ────────────────────────────────────────────
# AACF — 应用注册表 (Flask-style) / App registry
# ─────────────────────────────────────────────


class AACF:
    """
    AACF 应用实例，类似 Flask / AACF application instance, Flask-style.

    作为智能体节点的中心注册表，管理全局 LLM 配置和节点路由。
    Acts as the central registry for agent nodes, managing global LLM config and node routing.

    Usage::

        from aacf import AACF, LLMConfig

        app = AACF(__name__, config=LLMConfig(model="qwen2.5-7b", url="..."))

        @app.node(who="科幻小说作家", what="写短篇科幻微小说")
        def story_writer(topic: str):
            pass

        result = story_writer(topic="赛博朋克")
    """

    def __init__(self, name: str, config: LLMConfig = None):
        """
        创建一个新的 AACF 应用实例 / Create a new AACF application instance.

        Args:
            name: 应用名称，推荐使用 ``__name__`` / App name, recommend using ``__name__``
            config: 全局 LLM 配置，所有通过 ``@app.node`` 注册的节点都会
                    自动继承此配置，无需在调用时手动传入 / Global LLM config; all nodes
                    registered via ``@app.node`` will auto-inherit this config.
        """
        self.name = name
        self.config = config
        self._compiler = DependencyAnalyzer()
        self._compiled = False
        self._plan = None
        self._wrappers: Dict[str, typing.Callable] = {}

    def node(self, name: str) -> NodeBuilder:
        """
        创建节点构建器（链式调用 API）/ Create node builder (chainable API).

        统一使用链式调用，IDE 自动补全友好，无需记忆参数名。
        Uses chainable API exclusively — IDE auto-completion friendly, no need to memorize parameter names.

        Usage::

            # 方式 1：作为装饰器 / As decorator
            @app.node("translator")
            def translator(text: str):
                pass

            # 方式 2：链式配置 / Chainable configuration
            translator = (
                app.node("translator")
                .who("翻译员")
                .what("翻译文本")
                .cache(ttl=300)
                .build()
            )

            # 方式 3：动态配置 / Dynamic configuration
            builder = app.node("translator").who("翻译员").what("翻译文本")
            if need_cache:
                builder = builder.cache(ttl=300)
            translator = builder.build()

        Args:
            name: 节点名称 / Node name

        Returns:
            NodeBuilder 实例 / NodeBuilder instance
        """
        return NodeBuilder(self, name)

    def _create_node_decorator(
        self,
        who: str = "",
        where: str = "",
        what: str = "",
        why: str = "",
        how: typing.Union[str, typing.List[str]] = "",
        module: typing.Union[str, typing.List[typing.Callable]] = "",
        out: str = "",
        stream: bool = False,
        format: str = "",
        cache_enabled: bool = False,
        cache_ttl: int = 0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        timeout: int = 0,
        branches: Optional[Dict[str, typing.Callable]] = None,
    ) -> typing.Callable:
        """
        核心装饰器：将普通函数转化为 LLM 驱动的智能节点 / Core decorator: transforms a plain function into an LLM-driven smart node.

        被装饰的函数体可以为 ``pass``，框架会自动拦截入参、构建 Prompt
        并调用 LLM。如果函数体有实际代码，则优先执行用户代码（显式代码覆盖）。
        Decorated function body can be ``pass`` (framework auto-builds prompt and calls LLM),
        or contain actual code (explicit override — user's code takes priority).

        Args:
            who: 智能体角色设定 / Agent role (e.g., ``"科幻小说家"`` / ``"Sci-Fi Writer"``)
            where: 业务环境或上下文 / Business context (e.g., ``"创意写作工坊"``)
            what: 核心任务描述 / Core task description (e.g., ``"写一段科幻微小说"``)
            why: 执行意图或业务原因 / Execution intent or business reason
            how: 操作步骤、方法或可选项 / Operational steps, methods, or options
            module: 智能路由模式——传入下级节点函数列表，本节点将升级为路由中心 /
                    Smart routing mode — pass sub-node function list, upgrades this node to a router
            out: 输出格式的补充要求 / Additional output format requirements
            stream: 是否开启流式响应，为 ``True`` 时返回 ``Generator`` /
                    Enable streaming response; returns ``Generator`` when ``True``
            format: 强制输出格式，``"json"`` 时开启 JSON 约束模式 /
                    Force output format; ``"json"`` enables JSON constraint mode
            cache_enabled: 是否启用结果缓存 / Enable result caching (default: False)
            cache_ttl: 缓存有效期（秒），0 表示永不过期 / Cache TTL in seconds, 0 = no expiry (default: 0)
            max_retries: 失败时最大重试次数 / Maximum retry attempts on failure (default: 3)
            retry_delay: 重试间隔（秒） / Delay in seconds between retries (default: 1.0)
            timeout: 执行超时（秒），0 表示无超时 / Execution timeout in seconds, 0 = no timeout (default: 0)
            branches: 条件分支路由——字典映射条件键到分支节点函数 /
                      Conditional branch routing — dict mapping condition keys to branch node functions.
                      The decorated function should return a string key to select which branch to execute.
                      被装饰函数应返回一个字符串键，用于选择执行哪个分支。

        Returns:
            装饰后的代理函数，入参不变，输出为 LLM 回复（``str`` 或 ``Generator``）/
            Decorated proxy function; same inputs, output is LLM response (``str`` or ``Generator``)
        """

        def decorator(func):
            sig = inspect.signature(func)

            is_pass_only = _is_function_body_pass(func)

            @wraps(func)
            def wrapper(*args, **kwargs):
                # 显式代码覆盖：函数体有实际代码时，优先执行用户代码
                # Explicit code override: if function body has actual code, execute user's code first
                if not is_pass_only:
                    result = func(*args, **kwargs)
                    # 如果有条件分支，根据返回值路由到对应分支
                    # If conditional branches exist, route to corresponding branch based on return value
                    if branches and isinstance(result, str) and result in branches:
                        branch_func = branches[result]
                        return branch_func(*args, **kwargs)
                    return result

                call_llm_config = kwargs.pop("llm_config", None)

                try:
                    bound_args = sig.bind(*args, **kwargs)
                    bound_args.apply_defaults()
                    user_prompt_dict = dict(bound_args.arguments)
                except TypeError:
                    user_prompt_dict = kwargs.copy()
                    for i, arg in enumerate(args):
                        user_prompt_dict[f"arg_{i}"] = arg

                func_llm_config = user_prompt_dict.pop("llm_config", None)
                final_config = call_llm_config or func_llm_config or self.config

                lang = "zh"
                if final_config and hasattr(final_config, "get_language"):
                    lang = final_config.get_language()
                elif final_config and isinstance(final_config, dict):
                    lang = final_config.get("language", "zh")

                tpl = PROMPT_TEMPLATES.get(lang, PROMPT_TEMPLATES["zh"])

                prompt = tpl["role"].format(
                    who=who or "AI Assistant", where=where or "workspace", what=what or "helpful assistant"
                )
                if why:
                    prompt += tpl["intent"].format(why=why)
                if how:
                    prompt += tpl["how"].format(how=how)

                module_str = ""
                if module:
                    if isinstance(module, list):
                        module_str = ", ".join(m.__name__ if hasattr(m, "__name__") else str(m) for m in module)
                    else:
                        module_str = str(module)

                if module_str:
                    prompt += tpl["routing_header"]
                    prompt += tpl["routing_modules"].format(modules=module_str)
                    prompt += tpl["routing_instruction"]
                    prompt += tpl["routing_format"]
                    prompt += tpl["routing_example"]
                    prompt += tpl["routing_fallback"]

                prompt += tpl["output_request"]
                if out:
                    prompt += tpl["output_requirement"].format(out=out)

                user_prompt = str(user_prompt_dict)
                is_json = format.lower() == "json"

                result = llm_call(
                    system_prompt=prompt,
                    user_prompt=user_prompt,
                    temperature=0.7,
                    stream=stream,
                    json_mode=is_json,
                    llm_config=final_config,
                )

                # 如果有条件分支，根据 LLM 返回值路由到对应分支
                # If conditional branches exist, route to corresponding branch based on LLM return value
                if branches and isinstance(result, str) and result in branches:
                    branch_func = branches[result]
                    return branch_func(*args, **kwargs)

                return result

            # 缓存配置存入元数据，供管道执行时使用
            # Cache config stored in metadata for pipeline execution
            wrapper.__aacf_meta__ = {
                "who": who,
                "what": what,
                "where": where,
                "why": why,
                "how": how,
                "module": module,
                "out": out,
                "stream": stream,
                "format": format,
                "cache_enabled": cache_enabled,
                "cache_ttl": cache_ttl,
                "max_retries": max_retries,
                "retry_delay": retry_delay,
                "timeout": timeout,
                "branches": branches,
            }

            filepath = inspect.getsourcefile(func)
            if filepath:
                if filepath not in _AACF_NODE_REGISTRY:
                    _AACF_NODE_REGISTRY[filepath] = []
                _AACF_NODE_REGISTRY[filepath].append((func, wrapper.__aacf_meta__, sig))

                global _AACF_ATEXIT_REGISTERED
                if not _AACF_ATEXIT_REGISTERED:
                    atexit.register(_inject_docstrings_on_exit)
                    _AACF_ATEXIT_REGISTERED = True

            # Register with compiler for dependency analysis
            self._compiler.register_from_aacf_meta(func.__name__, func, wrapper.__aacf_meta__)
            # Store wrapper for pipeline execution
            self._wrappers[func.__name__] = wrapper

            return wrapper

        return decorator

    def compile(self) -> ExecutionPlanner:
        """
        预编译：分析所有已注册节点的依赖关系，构建 DAG，生成执行计划。
        Pre-compile: analyze dependencies of all registered nodes, build DAG, generate execution plan.

        在运行时前调用此方法，框架将：
        1. 解析每个节点的参数和返回值
        2. 推断节点间的输入输出依赖关系
        3. 构建有向无环图 (DAG)
        4. 生成拓扑执行顺序和并行分组

        Call this before runtime. The framework will:
        1. Parse each node's parameters and return types
        2. Infer input/output dependencies between nodes
        3. Build a Directed Acyclic Graph (DAG)
        4. Generate topological execution order and parallel groups

        Returns:
            ExecutionPlanner 实例，可查询执行计划 / ExecutionPlanner instance for querying execution plan

        Raises:
            ValueError: 如果检测到循环依赖 / If circular dependency detected
        """
        self._compiler.analyze()
        planner = ExecutionPlanner(self._compiler)
        self._plan = planner.create_plan()
        self._compiled = True
        return planner

    def get_execution_order(self) -> List[str]:
        """
        获取节点拓扑执行顺序 / Get topological execution order of nodes.

        Returns:
            按依赖关系排序的节点名列表 / Node names sorted by dependency order
        """
        if not self._compiled:
            self.compile()
        return self._compiler.get_execution_order()

    def get_parallel_groups(self) -> List[List[str]]:
        """
        获取可并行执行的节点分组 / Get groups of nodes that can execute in parallel.

        Returns:
            列表的列表，每组内的节点可同时执行 / List of lists, nodes within each group can run simultaneously
        """
        if not self._compiled:
            self.compile()
        return self._compiler.get_parallel_groups()

    def get_dependency_graph(self) -> Dict[str, Set[str]]:
        """
        获取依赖图 / Get the dependency graph.

        Returns:
            节点名到其依赖节点集合的映射 / Mapping of node name to its dependency set
        """
        if not self._compiled:
            self.compile()
        return self._compiler.get_dependency_graph()

    def run_pipeline(
        self,
        inputs: Optional[Dict[str, Dict[str, Any]]] = None,
        node_config: Optional[AtomicNodeConfig] = None,
    ) -> Dict[str, Any]:
        """
        Execute all registered nodes as an atomic pipeline.
        将所有已注册节点作为原子化管道执行。

        Builds an AtomicScheduler from dependency analysis, wraps each node
        as an AtomicNode, and executes them in dependency order. Dependency
        results are automatically injected into downstream node parameters.
        根据依赖分析构建 AtomicScheduler，将每个节点包装为 AtomicNode，
        按依赖顺序执行。依赖结果自动注入到下游节点参数中。

        Args:
            inputs: Per-node input data. Keys are node names, values are
                    dicts of parameter names to values.
                    每个节点的输入数据。键为节点名，值为参数名到值的字典。
            node_config: Default AtomicNodeConfig for all nodes. Can be
                        overridden per-node in future versions.
                        所有节点的默认 AtomicNodeConfig。未来版本可支持按节点覆盖。

        Returns:
            Dict mapping node name to execution result.
            节点名到执行结果的映射。

        Raises:
            RuntimeError: If any node fails after retries.
                         如果任何节点在重试后仍然失败。

        Example::

            app = AACF(__name__)

            @app.node(who="Extractor", what="Extract data")
            def extractor(text: str):
                pass

            @app.node(who="Summarizer", what="Summarize")
            def summarizer(extractor: str):  # param name matches node name
                pass

            results = app.run_pipeline(inputs={"extractor": {"text": "..."}})
            print(results["summarizer"])
        """
        if not self._compiled:
            self.compile()

        scheduler = AtomicScheduler()

        # Build AtomicNodes from compiler dependency info
        for node_name, node_info in self._compiler.nodes.items():
            if node_name not in self._wrappers:
                continue

            wrapper = self._wrappers[node_name]
            dependencies = node_info.dependencies

            # 从装饰器元数据中读取缓存配置，优先使用节点级配置
            # Read cache config from decorator metadata, node-level config takes priority
            meta = wrapper.__aacf_meta__
            node_atomic_config = AtomicNodeConfig(
                cache_enabled=meta.get("cache_enabled", False),
                cache_ttl=meta.get("cache_ttl", 0),
                max_retries=meta.get("max_retries", 3),
                retry_delay=meta.get("retry_delay", 1.0),
                timeout=meta.get("timeout", 0),
            )

            # 如果传入了全局 node_config，则使用全局配置覆盖节点配置
            # If global node_config is provided, it overrides node-level config
            final_config = node_config or node_atomic_config

            scheduler.add_node(
                name=node_name,
                func=wrapper,
                config=final_config,
                dependencies=dependencies,
                params=node_info.params,
            )

        # Execute pipeline
        return scheduler.run_all(inputs=inputs)

    def run_pipeline_parallel(
        self,
        inputs: Optional[Dict[str, Dict[str, Any]]] = None,
        node_config: Optional[AtomicNodeConfig] = None,
        max_workers: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Execute all registered nodes as a parallel pipeline.
        将所有已注册节点作为并行管道执行。

        Independent nodes (no dependencies between them) execute concurrently
        using a thread pool. Dependent groups execute sequentially.
        独立节点（彼此无依赖）使用线程池并发执行。有依赖的组串行执行。

        Args:
            inputs: Per-node input data / 每个节点的输入数据
            node_config: Default AtomicNodeConfig for all nodes / 所有节点的默认配置
            max_workers: Maximum thread pool size / 线程池最大线程数

        Returns:
            Dict mapping node name to execution result / 节点名到执行结果的映射
        """
        if not self._compiled:
            self.compile()

        scheduler = AtomicScheduler()

        for node_name, node_info in self._compiler.nodes.items():
            if node_name not in self._wrappers:
                continue

            wrapper = self._wrappers[node_name]
            dependencies = node_info.dependencies

            # 从装饰器元数据中读取缓存配置，优先使用节点级配置
            # Read cache config from decorator metadata, node-level config takes priority
            meta = wrapper.__aacf_meta__
            node_atomic_config = AtomicNodeConfig(
                cache_enabled=meta.get("cache_enabled", False),
                cache_ttl=meta.get("cache_ttl", 0),
                max_retries=meta.get("max_retries", 3),
                retry_delay=meta.get("retry_delay", 1.0),
                timeout=meta.get("timeout", 0),
            )

            # 如果传入了全局 node_config，则使用全局配置覆盖节点配置
            # If global node_config is provided, it overrides node-level config
            final_config = node_config or node_atomic_config

            scheduler.add_node(
                name=node_name,
                func=wrapper,
                config=final_config,
                dependencies=dependencies,
                params=node_info.params,
            )

        return scheduler.run_parallel(inputs=inputs, max_workers=max_workers)

    def get_node_status(self, node_name: str) -> Optional[NodeStatus]:
        """
        Get the execution status of a specific node.
        获取指定节点的执行状态。

        Args:
            node_name: Node name / 节点名

        Returns:
            NodeStatus if node exists, None otherwise.
            节点状态（如果存在），否则为 None。
        """
        if not self._compiled:
            return None
        node_info = self._compiler.nodes.get(node_name)
        return node_info.status if node_info else None

    def get_all_node_statuses(self) -> Dict[str, NodeStatus]:
        """
        Get execution status of all registered nodes.
        获取所有已注册节点的执行状态。

        Returns:
            Dict mapping node name to NodeStatus.
            节点名到 NodeStatus 的映射。
        """
        if not self._compiled:
            return {}
        return {name: info.status for name, info in self._compiler.nodes.items()}
