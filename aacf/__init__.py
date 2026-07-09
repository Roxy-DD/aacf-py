# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 AACF Contributors
#
# AACF — Agentic AI Compiler Framework / 智能体编译器框架
#
# AI workflow pre-compilation and highly controllable scheduling execution engine.
# AI 工作流预编译与高度可控的调度执行引擎。
#
# Exports / 导出:
#     AACF: Application registry with @app.node() decorator / 应用注册表与节点装饰器
#     LLMConfig: LLM call configuration / 大模型调用配置
#     NodeStatus: Node execution status enum / 节点执行状态枚举
#     AtomicNodeConfig: Atomic node execution configuration / 原子节点执行配置
#     ExecutionResult: Rust-style execution result / Rust 风格的执行结果
#     AACFError: Base error class / 基础错误类
#     CircularDependencyError: Circular dependency error / 循环依赖错误
#     NodeExecutionError: Node execution error / 节点执行错误
#     PipelineError: Pipeline-level error / 管道级错误
#     DAGCache: Incremental cache for DAG execution / DAG 执行增量缓存
#     DAGVisualizer: Interactive HTML visualization / 交互式 HTML 可视化

from aacf.core import AACF, LLMConfig
from aacf.compiler import (
    AtomicNodeConfig, NodeStatus,
    ExecutionResult,
    AACFError, CircularDependencyError, NodeExecutionError, PipelineError,
    DAGCache,
)

try:
    from aacf.visualize import DAGVisualizer
except ImportError:
    # pyvis not installed / pyvis 未安装
    DAGVisualizer = None  # type: ignore

__all__ = [
    "AACF", "LLMConfig",
    "NodeStatus", "AtomicNodeConfig",
    "ExecutionResult",
    "AACFError", "CircularDependencyError", "NodeExecutionError", "PipelineError",
    "DAGCache", "DAGVisualizer",
]
