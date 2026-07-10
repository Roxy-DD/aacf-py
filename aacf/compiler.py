# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2024 AACF Contributors
"""
AACF Compiler — Data dependency analysis and DAG construction.
AACF 编译器 — 数据依赖分析与 DAG 构建。

This module provides:
- Dependency analysis: Parse function parameters and return types to infer node relationships
- DAG construction: Build directed acyclic graph based on dependencies
- Execution planning: Generate topological execution order

本模块提供：
- 依赖分析：解析函数参数与返回值，推断节点关系
- DAG 构建：根据依赖关系构建有向无环图
- 执行计划：生成拓扑执行顺序
"""
import ast
import hashlib
import inspect
import json
import typing
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


# ─────────────────────────────────────────────
# Error Hierarchy — Rust 风格错误类型 / Rust-style error types
# ─────────────────────────────────────────────

class AACFError(Exception):
    """
    Base error for all AACF errors / AACF 所有错误的基类。

    Following Rust's philosophy: errors are explicit, typed, and carry context.
    遵循 Rust 哲学：错误是显式的、有类型的、携带上下文的。
    """
    pass


class CircularDependencyError(AACFError):
    """
    Circular dependency detected in DAG / DAG 中检测到循环依赖。

    Attributes:
        cycle: List of node names forming the cycle / 构成循环的节点名列表
    """
    def __init__(self, cycle: List[str]):
        self.cycle = cycle
        cycle_str = " -> ".join(cycle)
        super().__init__(
            f"Circular dependency detected / 检测到循环依赖: {cycle_str}"
        )


class DependencyError(AACFError):
    """
    Dependency resolution error (e.g., missing dependency) / 依赖解析错误（如缺少依赖）。
    """
    pass


class NodeExecutionError(AACFError):
    """
    Node execution failed after all retries / 节点执行失败（所有重试耗尽）。

    Attributes:
        node_name: Name of the failed node / 失败节点名
        attempts: Number of attempts made / 尝试次数
        cause: Original error message / 原始错误信息
    """
    def __init__(self, node_name: str, attempts: int, cause: str):
        self.node_name = node_name
        self.attempts = attempts
        self.cause = cause
        super().__init__(
            f"Node '{node_name}' failed after {attempts} attempts / "
            f"节点 '{node_name}' 在 {attempts} 次尝试后失败: {cause}"
        )


class NodeConfigError(AACFError):
    """
    Invalid node configuration / 节点配置无效。
    """
    pass


class PipelineError(AACFError):
    """
    Pipeline-level error (e.g., blocked execution) / 管道级错误（如执行阻塞）。
    """
    pass


class ExecutionResult:
    """
    Rust-style Result<T, E> for node execution / Rust 风格的节点执行结果。

    Instead of throwing exceptions, node execution returns this Result object.
    Callers must explicitly handle success/failure, following Rust's philosophy
    of making error handling visible and mandatory.
    不抛出异常，节点执行返回此 Result 对象。
    调用者必须显式处理成功/失败，遵循 Rust 哲学使错误处理可见且强制。

    Usage::

        result = node.execute(input_data)
        if result.is_ok():
            print(result.unwrap())
        else:
            print(result.error_info())

        # Pattern matching style / 模式匹配风格
        match result:
            case ExecutionResult() if result.is_ok():
                handle(result.value)
            case ExecutionResult() if result.is_err():
                handle_error(result.error)
    """

    def __init__(
        self,
        ok: bool,
        value: Any = None,
        error: Optional[str] = None,
        node_name: str = "",
        attempts: int = 0,
        from_cache: bool = False,
    ):
        """
        Initialize execution result / 初始化执行结果。

        Args:
            ok: Whether execution succeeded / 执行是否成功
            value: Result value (if successful) / 结果值（成功时）
            error: Error message (if failed) / 错误信息（失败时）
            node_name: Name of the executed node / 执行的节点名
            attempts: Number of execution attempts / 执行尝试次数
            from_cache: Whether result was served from cache / 结果是否来自缓存
        """
        self._ok = ok
        self._value = value
        self._error = error
        self._node_name = node_name
        self._attempts = attempts
        self._from_cache = from_cache

    @staticmethod
    def success(value: Any, node_name: str = "", attempts: int = 1, from_cache: bool = False) -> 'ExecutionResult':
        """Create a success result / 创建成功结果。"""
        return ExecutionResult(ok=True, value=value, node_name=node_name, attempts=attempts, from_cache=from_cache)

    @staticmethod
    def failure(error: str, node_name: str = "", attempts: int = 1) -> 'ExecutionResult':
        """Create a failure result / 创建失败结果。"""
        return ExecutionResult(ok=False, error=error, node_name=node_name, attempts=attempts)

    def is_ok(self) -> bool:
        """Check if execution succeeded / 检查执行是否成功。"""
        return self._ok

    def is_err(self) -> bool:
        """Check if execution failed / 检查执行是否失败。"""
        return not self._ok

    @property
    def value(self) -> Any:
        """
        Get the result value / 获取结果值。

        Raises:
            NodeExecutionError: If execution failed / 如果执行失败
        """
        if not self._ok:
            raise NodeExecutionError(self._node_name, self._attempts, self._error or "Unknown error")
        return self._value

    @property
    def error(self) -> Optional[str]:
        """Get the error message (None if successful) / 获取错误信息（成功时为 None）。"""
        return self._error

    @property
    def node_name(self) -> str:
        """Get the node name / 获取节点名。"""
        return self._node_name

    @property
    def attempts(self) -> int:
        """Get the number of attempts / 获取尝试次数。"""
        return self._attempts

    @property
    def from_cache(self) -> bool:
        """Whether result was served from cache / 结果是否来自缓存。"""
        return self._from_cache

    def unwrap(self) -> Any:
        """
        Unwrap the value, panicking on error (Rust-style) / 解包值，失败时恐慌（Rust 风格）。

        Returns:
            The result value / 结果值

        Raises:
            NodeExecutionError: If execution failed / 如果执行失败
        """
        return self.value

    def unwrap_or(self, default: Any) -> Any:
        """
        Return value if ok, otherwise return default / 成功时返回值，否则返回默认值。

        Args:
            default: Default value to return on failure / 失败时返回的默认值
        """
        return self._value if self._ok else default

    def unwrap_or_raise(self) -> Any:
        """
        Unwrap the value, raising NodeExecutionError on failure / 解包值，失败时抛出 NodeExecutionError。

        Returns:
            The result value / 结果值

        Raises:
            NodeExecutionError: If execution failed / 如果执行失败
        """
        if not self._ok:
            raise NodeExecutionError(self._node_name, self._attempts, self._error or "Unknown error")
        return self._value

    def error_info(self) -> Dict[str, Any]:
        """
        Get structured error information / 获取结构化错误信息。

        Returns:
            Dict with error details / 包含错误详情的字典
        """
        return {
            "node_name": self._node_name,
            "error": self._error,
            "attempts": self._attempts,
            "ok": self._ok,
        }

    def map(self, func: typing.Callable) -> 'ExecutionResult':
        """
        Apply a function to the value if ok (Rust-style) / 成功时对值应用函数（Rust 风格）。

        Args:
            func: Function to apply to the value / 应用于值的函数

        Returns:
            New ExecutionResult with transformed value / 包含转换值的新 ExecutionResult
        """
        if self._ok:
            try:
                new_value = func(self._value)
                return ExecutionResult.success(new_value, self._node_name, self._attempts, self._from_cache)
            except Exception as e:
                return ExecutionResult.failure(str(e), self._node_name, self._attempts)
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary / 序列化为字典。"""
        return {
            "ok": self._ok,
            "node_name": self._node_name,
            "value": self._value if self._ok else None,
            "error": self._error,
            "attempts": self._attempts,
            "from_cache": self._from_cache,
        }

    def __repr__(self) -> str:
        if self._ok:
            cache_tag = " (cached)" if self._from_cache else ""
            return f"Ok({self._value!r}){cache_tag}"
        return f"Err({self._error!r})"


class NodeStatus(Enum):
    """Node execution status / 节点执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class NodeInfo:
    """
    Metadata for an AACF node / AACF 节点元数据。

    Attributes:
        name: Function name / 函数名
        func: Original function object / 原始函数对象
        params: Parameter names / 参数名列表
        return_type: Return type annotation / 返回值类型注解
        dependencies: Set of node names this node depends on / 依赖的节点名集合
        dependents: Set of node names that depend on this node / 依赖此节点的节点名集合
        status: Current execution status / 当前执行状态
        result: Execution result (if completed) / 执行结果（如已完成）
    """
    name: str
    func: Any = None
    params: List[str] = field(default_factory=list)
    return_type: Optional[str] = None
    dependencies: Set[str] = field(default_factory=set)
    dependents: Set[str] = field(default_factory=set)
    status: NodeStatus = NodeStatus.PENDING
    result: Any = None


class DependencyAnalyzer:
    """
    Analyze data dependencies between AACF nodes.
    分析 AACF 节点间的数据依赖关系。

    Usage::

        analyzer = DependencyAnalyzer()
        analyzer.register_node("extractor", extractor_func, params=["text"], return_type="dict")
        analyzer.register_node("summarizer", summarizer_func, params=["data"], return_type="str")
        analyzer.analyze()
        print(analyzer.get_execution_order())
    """

    def __init__(self):
        self.nodes: Dict[str, NodeInfo] = {}
        self._analyzed = False

    def register_node(
        self,
        name: str,
        func: Any = None,
        params: Optional[List[str]] = None,
        return_type: Optional[str] = None,
    ) -> None:
        """
        Register a node for dependency analysis.
        注册节点以进行依赖分析。

        Args:
            name: Node name (function name) / 节点名（函数名）
            func: Function object (optional, for auto-extraction) / 函数对象（可选，用于自动提取）
            params: Parameter names (if None, extracted from func) / 参数名（如为 None，从 func 提取）
            return_type: Return type annotation / 返回值类型注解
        """
        if params is None and func is not None:
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())

        if return_type is None and func is not None:
            sig = inspect.signature(func)
            if sig.return_annotation != inspect.Parameter.empty:
                return_type = str(sig.return_annotation)

        self.nodes[name] = NodeInfo(
            name=name,
            func=func,
            params=params or [],
            return_type=return_type,
        )
        self._analyzed = False

    def register_from_aacf_meta(self, name: str, func: Any, meta: Dict[str, Any]) -> None:
        """
        Register a node from AACF decorator metadata.
        从 AACF 装饰器元数据注册节点。

        Args:
            name: Node name / 节点名
            func: Function object / 函数对象
            meta: Decorator metadata (__aacf_meta__) / 装饰器元数据
        """
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())

        return_type = None
        if sig.return_annotation != inspect.Parameter.empty:
            return_type = str(sig.return_annotation)

        self.register_node(name, func, params, return_type)

        # Store module dependencies for smart routing
        if meta.get("module"):
            module_list = meta["module"]
            if isinstance(module_list, list):
                for mod_func in module_list:
                    if hasattr(mod_func, "__name__"):
                        self.nodes[name].dependencies.add(mod_func.__name__)

    def analyze(self) -> None:
        """
        Analyze dependencies between all registered nodes.
        分析所有已注册节点间的依赖关系。

        Currently uses parameter name matching to infer dependencies.
        If node A's parameter name matches node B's name, A depends on B.
        当前使用参数名匹配来推断依赖关系。
        如果节点 A 的参数名与节点 B 的名称匹配，则 A 依赖 B。
        """
        # Clear existing dependency info
        for node in self.nodes.values():
            node.dependencies = set()
            node.dependents = set()

        # Build dependency graph based on parameter names
        for node_name, node_info in self.nodes.items():
            for param in node_info.params:
                # Check if any other node's name matches this parameter
                for other_name in self.nodes:
                    if other_name != node_name and other_name == param:
                        node_info.dependencies.add(other_name)
                        self.nodes[other_name].dependents.add(node_name)

        self._analyzed = True

    def get_execution_order(self) -> List[str]:
        """
        Get topological execution order (Kahn's algorithm).
        获取拓扑执行顺序（Kahn 算法）。

        Returns:
            List of node names in execution order / 按执行顺序排列的节点名列表

        Raises:
            ValueError: If circular dependency detected / 如果检测到循环依赖
        """
        if not self._analyzed:
            self.analyze()

        # Calculate in-degree
        in_degree = {name: 0 for name in self.nodes}
        for node in self.nodes.values():
            for dep in node.dependencies:
                if dep in in_degree:
                    in_degree[node.name] += 1

        # Start with nodes that have no dependencies
        queue = deque([name for name, degree in in_degree.items() if degree == 0])
        order = []

        while queue:
            node_name = queue.popleft()
            order.append(node_name)

            # Reduce in-degree for dependents
            for dependent in self.nodes[node_name].dependents:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(order) != len(self.nodes):
            # Find cycle for better error message
            remaining = set(self.nodes.keys()) - set(order)
            cycle = self._find_cycle(list(remaining))
            raise CircularDependencyError(cycle)

        return order

    def _find_cycle(self, start_nodes: List[str]) -> List[str]:
        """
        Find a cycle in the graph starting from given nodes.
        从给定节点开始查找图中的循环。

        Args:
            start_nodes: Nodes to start search from / 开始搜索的节点

        Returns:
            List of node names forming the cycle / 构成循环的节点名列表
        """
        visited = set()
        path = []

        def dfs(node: str) -> bool:
            if node in visited:
                # Found cycle
                cycle_start = path.index(node)
                return path[cycle_start:] + [node]
            visited.add(node)
            path.append(node)
            for dep in self.nodes[node].dependencies:
                if dep in self.nodes:
                    result = dfs(dep)
                    if result:
                        return result
            path.pop()
            return []

        for node in start_nodes:
            if node not in visited:
                cycle = dfs(node)
                if cycle:
                    return cycle
        return start_nodes[:2] + [start_nodes[0]] if len(start_nodes) >= 2 else start_nodes

    def get_dependency_graph(self) -> Dict[str, Set[str]]:
        """
        Get the dependency graph as adjacency list.
        获取依赖图的邻接表表示。

        Returns:
            Dict mapping node name to set of dependencies / 节点名到依赖集合的映射
        """
        if not self._analyzed:
            self.analyze()

        return {name: info.dependencies.copy() for name, info in self.nodes.items()}

    def get_parallel_groups(self) -> List[List[str]]:
        """
        Get groups of nodes that can execute in parallel.
        获取可并行执行的节点组。

        Returns:
            List of lists, each inner list contains nodes that can run simultaneously /
            列表的列表，每个内部列表包含可同时运行的节点
        """
        if not self._analyzed:
            self.analyze()

        # Calculate in-degree
        in_degree = {name: 0 for name in self.nodes}
        for node in self.nodes.values():
            for dep in node.dependencies:
                if dep in in_degree:
                    in_degree[node.name] += 1

        groups = []
        remaining = set(self.nodes.keys())

        while remaining:
            # Find all nodes with in-degree 0
            group = [name for name in remaining if in_degree[name] == 0]
            if not group:
                # Find cycle for better error message / 查找循环以提供更好的错误信息
                remaining_list = list(remaining)
                cycle = self._find_cycle(remaining_list)
                raise CircularDependencyError(cycle)

            groups.append(sorted(group))

            # Remove these nodes and update in-degrees
            for node_name in group:
                remaining.remove(node_name)
                for dependent in self.nodes[node_name].dependents:
                    if dependent in remaining:
                        in_degree[dependent] -= 1

        return groups

    def validate_dag(self) -> bool:
        """
        Check if the dependency graph is a valid DAG (no cycles).
        检查依赖图是否为有效的 DAG（无循环）。

        Returns:
            True if valid DAG, False otherwise / 如果是有效 DAG 返回 True，否则返回 False
        """
        try:
            self.get_execution_order()
            return True
        except (ValueError, CircularDependencyError):
            return False

    def compute_dag_hash(self) -> str:
        """
        Compute a hash of the current DAG structure for change detection.
        计算当前 DAG 结构的哈希值用于变更检测。

        Returns:
            SHA256 hash of the DAG structure / DAG 结构的 SHA256 哈希值
        """
        if not self._analyzed:
            self.analyze()

        # Create a canonical representation of the DAG
        dag_data = {
            name: sorted(list(info.dependencies))
            for name, info in sorted(self.nodes.items())
        }

        # Serialize to JSON and compute hash
        dag_json = json.dumps(dag_data, sort_keys=True)
        return hashlib.sha256(dag_json.encode()).hexdigest()


class ExecutionPlanner:
    """
    Plan execution of AACF nodes based on dependency analysis.
    基于依赖分析规划 AACF 节点的执行。

    Usage::

        planner = ExecutionPlanner(analyzer)
        plan = planner.create_plan()
        for step in plan:
            print(f"Execute: {step}")
    """

    def __init__(self, analyzer: DependencyAnalyzer):
        self.analyzer = analyzer
        self._plan: List[Dict[str, Any]] = []

    def create_plan(self) -> List[Dict[str, Any]]:
        """
        Create an execution plan.
        创建执行计划。

        Returns:
            List of execution steps, each containing node name and dependencies /
            执行步骤列表，每个包含节点名和依赖
        """
        order = self.analyzer.get_execution_order()
        self._plan = []

        for node_name in order:
            node_info = self.analyzer.nodes[node_name]
            self._plan.append({
                "name": node_name,
                "dependencies": list(node_info.dependencies),
                "params": node_info.params,
                "status": NodeStatus.PENDING,
            })

        return self._plan

    def get_next_ready(self) -> List[str]:
        """
        Get nodes that are ready to execute (all dependencies satisfied).
        获取准备执行的节点（所有依赖已满足）。

        Returns:
            List of node names ready to execute / 准备执行的节点名列表
        """
        ready = []
        for step in self._plan:
            if step["status"] == NodeStatus.PENDING:
                deps_satisfied = all(
                    any(s["name"] == dep and s["status"] == NodeStatus.DONE
                        for s in self._plan)
                    for dep in step["dependencies"]
                )
                if deps_satisfied:
                    ready.append(step["name"])
        return ready

    def mark_complete(self, node_name: str, result: Any = None) -> None:
        """
        Mark a node as completed.
        标记节点为已完成。

        Args:
            node_name: Node name / 节点名
            result: Execution result / 执行结果
        """
        for step in self._plan:
            if step["name"] == node_name:
                step["status"] = NodeStatus.DONE
                step["result"] = result
                break

    def mark_failed(self, node_name: str) -> None:
        """
        Mark a node as failed.
        标记节点为失败。

        Args:
            node_name: Node name / 节点名
        """
        for step in self._plan:
            if step["name"] == node_name:
                step["status"] = NodeStatus.FAILED
                break

    def is_complete(self) -> bool:
        """
        Check if all nodes have been executed.
        检查所有节点是否已执行。

        Returns:
            True if all nodes are done or failed / 如果所有节点都已完成或失败返回 True
        """
        return all(
            step["status"] in (NodeStatus.DONE, NodeStatus.FAILED)
            for step in self._plan
        )


# ─────────────────────────────────────────────
# Atomic Node — 原子化执行单元 / Atomic execution unit
# ─────────────────────────────────────────────

@dataclass
class AtomicNodeConfig:
    """
    Configuration for an atomic execution node.
    原子化执行节点的配置。

    Attributes:
        max_retries: Maximum retry attempts on failure / 失败时最大重试次数
        retry_delay: Delay in seconds between retries / 重试间隔（秒）
        cache_enabled: Whether to cache results / 是否启用结果缓存
        cache_ttl: Cache time-to-live in seconds (0 = no expiry) / 缓存有效期（秒，0 = 永不过期）
        timeout: Execution timeout in seconds (0 = no timeout) / 执行超时（秒，0 = 无超时）
    """
    max_retries: int = 3
    retry_delay: float = 1.0
    cache_enabled: bool = False
    cache_ttl: int = 0
    timeout: int = 0


class AtomicNode:
    """
    An atomic, independently schedulable, retryable, and cacheable execution unit.
    一个可独立调度、可重试、可缓存的原子化执行单元。

    Each node from the user's declaration is wrapped as an AtomicNode,
    providing isolated execution with retry logic, result caching, and status tracking.
    用户声明的每个节点被包装为 AtomicNode，提供独立执行、重试逻辑、结果缓存和状态跟踪。

    Usage::

        node = AtomicNode("my_node", func=my_func, config=AtomicNodeConfig(max_retries=3))
        result = node.execute(input_data={"text": "hello"})
    """

    def __init__(
        self,
        name: str,
        func: Any = None,
        config: Optional[AtomicNodeConfig] = None,
        dependencies: Optional[Set[str]] = None,
        params: Optional[List[str]] = None,
    ):
        self.name = name
        self.func = func
        self.config = config or AtomicNodeConfig()
        self.dependencies = dependencies or set()
        self.params = params or []
        self.status = NodeStatus.PENDING
        self.result: Any = None
        self.error: Optional[str] = None
        self.attempts = 0
        self._cache: Optional[Any] = None
        self._cache_time: float = 0

    def _is_cache_valid(self) -> bool:
        """Check if cached result is still valid / 检查缓存是否仍然有效"""
        if not self.config.cache_enabled or self._cache is None:
            return False
        if self.config.cache_ttl > 0:
            import time
            return (time.time() - self._cache_time) < self.config.cache_ttl
        return True

    def _clear_cache(self) -> None:
        """Clear the cached result / 清除缓存结果"""
        self._cache = None
        self._cache_time = 0

    def execute(self, input_data: Optional[Dict[str, Any]] = None, force: bool = False) -> ExecutionResult:
        """
        Execute this atomic node with retry logic and caching.
        执行此原子节点，带重试逻辑和缓存。

        Args:
            input_data: Input parameters for the node function / 节点函数的输入参数
            force: Force re-execution even if cached / 强制重新执行（即使有缓存）

        Returns:
            ExecutionResult: Rust-style result object / Rust 风格的结果对象
        """
        # Check cache first
        if not force and self._is_cache_valid():
            self.status = NodeStatus.DONE
            return ExecutionResult.success(self._cache, node_name=self.name, from_cache=True)

        self.status = NodeStatus.RUNNING
        self.attempts = 0
        last_error = None

        while self.attempts < self.config.max_retries:
            self.attempts += 1
            try:
                if self.func is None:
                    raise NodeExecutionError(self.name, self.attempts, "No function bound to node")

                kwargs = input_data or {}
                self.result = self.func(**kwargs)

                # Cache the result
                if self.config.cache_enabled:
                    import time
                    self._cache = self.result
                    self._cache_time = time.time()

                self.status = NodeStatus.DONE
                self.error = None
                return ExecutionResult.success(self.result, node_name=self.name, attempts=self.attempts)

            except Exception as e:
                last_error = str(e)
                self.error = last_error

                if self.attempts < self.config.max_retries:
                    import time
                    time.sleep(self.config.retry_delay)

        # All retries exhausted
        self.status = NodeStatus.FAILED
        return ExecutionResult.failure(last_error, node_name=self.name, attempts=self.attempts)

    def reset(self) -> None:
        """Reset node to pending state / 重置节点为待执行状态"""
        self.status = NodeStatus.PENDING
        self.result = None
        self.error = None
        self.attempts = 0

    def skip(self) -> None:
        """Mark node as skipped / 标记节点为已跳过"""
        self.status = NodeStatus.SKIPPED

    def to_dict(self) -> Dict[str, Any]:
        """Serialize node state to dictionary / 将节点状态序列化为字典"""
        return {
            "name": self.name,
            "status": self.status.value,
            "attempts": self.attempts,
            "error": self.error,
            "dependencies": list(self.dependencies),
        }


class AtomicScheduler:
    """
    Schedule and execute atomic nodes respecting dependency order.
    按依赖顺序调度和执行原子节点。

    Usage::

        scheduler = AtomicScheduler()
        scheduler.add_node("extractor", extractor_func)
        scheduler.add_node("summarizer", summarizer_func, dependencies={"extractor"})
        results = scheduler.run_all({"extractor": {"text": "..."}})
    """

    def __init__(self):
        self.nodes: Dict[str, AtomicNode] = {}
        self._results: Dict[str, Any] = {}

    def add_node(
        self,
        name: str,
        func: Any = None,
        config: Optional[AtomicNodeConfig] = None,
        dependencies: Optional[Set[str]] = None,
        params: Optional[List[str]] = None,
    ) -> AtomicNode:
        """
        Add an atomic node to the scheduler.
        向调度器添加原子节点。

        Args:
            name: Node name / 节点名
            func: Function to execute / 要执行的函数
            config: Execution configuration / 执行配置
            dependencies: Set of node names this node depends on / 依赖的节点名集合
            params: Function parameter names / 函数参数名列表

        Returns:
            The created AtomicNode / 创建的 AtomicNode
        """
        node = AtomicNode(name, func, config, dependencies, params)
        self.nodes[name] = node
        return node

    def get_ready_nodes(self) -> List[AtomicNode]:
        """
        Get nodes whose dependencies are all satisfied.
        获取所有依赖已满足的节点。

        Returns:
            List of AtomicNode instances ready to execute / 准备执行的 AtomicNode 列表
        """
        ready = []
        for node in self.nodes.values():
            if node.status != NodeStatus.PENDING:
                continue
            deps_met = all(
                dep in self._results and self.nodes[dep].status == NodeStatus.DONE
                for dep in node.dependencies
            )
            if deps_met:
                ready.append(node)
        return ready

    def _can_execute(self, node: AtomicNode, inputs: Dict[str, Dict[str, Any]]) -> bool:
        """
        Check if a node's parameters can be satisfied from inputs or dependency results.
        检查节点的参数是否能从输入或依赖结果中满足。

        Args:
            node: The atomic node to check / 要检查的原子节点
            inputs: Per-node input data / 每个节点的输入数据

        Returns:
            True if all required parameters can be provided / 如果所有必需参数都能提供则为 True
        """
        if not node.params:
            return True
        for param in node.params:
            has_from_input = param in inputs.get(node.name, {})
            has_from_dep = param in self._results
            if not has_from_input and not has_from_dep:
                return False
        return True

    def run_all(
        self,
        inputs: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Execute all nodes in dependency order (serial execution).
        按依赖顺序执行所有节点（串行执行）。

        Nodes whose parameters cannot be satisfied are skipped.
        参数无法满足的节点会被跳过。

        Args:
            inputs: Per-node input data / 每个节点的输入数据

        Returns:
            Dict mapping node name to execution result / 节点名到执行结果的映射

        Raises:
            PipelineError: If any node fails / 如果任何节点失败
        """
        inputs = inputs or {}
        self._results = {}

        while len(self._results) + len([n for n in self.nodes.values() if n.status == NodeStatus.SKIPPED]) < len(self.nodes):
            ready = self.get_ready_nodes()
            if not ready:
                # Check for failed nodes blocking progress
                failed = [n for n in self.nodes.values() if n.status == NodeStatus.FAILED]
                if failed:
                    raise PipelineError(
                        f"Execution blocked by failed node(s): {[n.name for n in failed]} / "
                        f"执行被失败的节点阻塞: {[n.name for n in failed]}"
                    )
                break

            for node in ready:
                # Skip nodes whose parameters cannot be satisfied
                if not self._can_execute(node, inputs):
                    node.status = NodeStatus.SKIPPED
                    continue

                node_input = inputs.get(node.name, {})
                # Inject dependency results into input
                for dep_name in node.dependencies:
                    if dep_name in self._results:
                        node_input[dep_name] = self._results[dep_name]

                result = node.execute(node_input)
                if result.is_err():
                    raise PipelineError(
                        f"Node '{node.name}' failed: {result.error} / 节点 '{node.name}' 失败: {result.error}"
                    )
                self._results[node.name] = result.unwrap()

        return self._results

    def run_parallel(
        self,
        inputs: Optional[Dict[str, Dict[str, Any]]] = None,
        max_workers: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Execute all nodes with parallel execution for independent nodes.
        并行执行所有节点，独立节点可并发执行。

        Nodes in the same parallel group (no dependencies between them) are
        executed concurrently using a thread pool. Groups are processed
        sequentially to respect dependency order.
        同一并行组中的节点（彼此无依赖）使用线程池并发执行。组按依赖顺序串行处理。

        Args:
            inputs: Per-node input data / 每个节点的输入数据
            max_workers: Maximum number of threads in the pool. If None,
                        uses Python's default (min(32, os.cpu_count() + 4)).
                        线程池最大线程数。如为 None，使用 Python 默认值。

        Returns:
            Dict mapping node name to execution result / 节点名到执行结果的映射

        Raises:
            PipelineError: If any node fails / 如果任何节点失败

        Example::

            scheduler = AtomicScheduler()
            scheduler.add_node("a", func_a)
            scheduler.add_node("b", func_b)  # independent of a
            scheduler.add_node("c", func_c, dependencies={"a", "b"})
            results = scheduler.run_parallel(max_workers=4)
            # a and b execute in parallel, then c
        """
        inputs = inputs or {}
        self._results = {}

        # Build dependency analyzer to get parallel groups
        analyzer = DependencyAnalyzer()
        for name, node in self.nodes.items():
            analyzer.register_node(name, params=list(node.dependencies))
        analyzer.analyze()

        try:
            groups = analyzer.get_parallel_groups()
        except (ValueError, CircularDependencyError) as e:
            raise PipelineError(f"Cannot execute: {e} / 无法执行: {e}")

        # Execute groups sequentially, nodes within group in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for group in groups:
                futures = {}
                for node_name in group:
                    node = self.nodes[node_name]
                    
                    # Skip nodes whose parameters cannot be satisfied
                    if not self._can_execute(node, inputs):
                        node.status = NodeStatus.SKIPPED
                        continue

                    node_input = inputs.get(node_name, {})

                    # Inject dependency results
                    for dep_name in node.dependencies:
                        if dep_name in self._results:
                            node_input[dep_name] = self._results[dep_name]

                    # Submit to thread pool
                    future = executor.submit(node.execute, node_input)
                    futures[future] = node_name

                # Wait for all nodes in this group to complete
                for future in as_completed(futures):
                    node_name = futures[future]
                    result = future.result()
                    if result.is_err():
                        raise PipelineError(
                            f"Node '{node_name}' failed: {result.error} / 节点 '{node_name}' 失败: {result.error}"
                        )
                    self._results[node_name] = result.unwrap()

        return self._results

    def get_status_summary(self) -> Dict[str, int]:
        """
        Get a summary of node execution statuses.
        获取节点执行状态摘要。

        Returns:
            Dict mapping status to count / 状态到数量的映射
        """
        summary = {s.value: 0 for s in NodeStatus}
        for node in self.nodes.values():
            summary[node.status.value] += 1
        return summary


# ─────────────────────────────────────────────
# DAG Cache — 增量缓存机制 / Incremental cache mechanism
# ─────────────────────────────────────────────

class DAGCache:
    """
    Incremental cache for DAG execution results with hash-based change detection.
    基于哈希变更检测的 DAG 执行结果增量缓存。

    This class implements a caching mechanism that:
    1. Computes a hash of the DAG structure (nodes + dependencies)
    2. Stores execution results keyed by DAG hash
    3. Detects changes by comparing hashes
    4. Only recomputes changed parts (incremental update)
    5. Avoids redundant computation for unchanged DAGs

    此类实现缓存机制：
    1. 计算 DAG 结构的哈希值（节点 + 依赖关系）
    2. 以 DAG 哈希为键存储执行结果
    3. 通过比较哈希检测变更
    4. 仅重新计算变更部分（增量更新）
    5. 避免对未变更 DAG 的重复计算

    Usage::

        cache = DAGCache()
        analyzer = DependencyAnalyzer()
        # ... register nodes ...
        dag_hash = analyzer.compute_dag_hash()

        if cache.has_valid_cache(dag_hash):
            results = cache.get(dag_hash)
        else:
            results = scheduler.run_all(inputs)
            cache.set(dag_hash, results, analyzer)
    """

    def __init__(self, max_cache_size: int = 100):
        """
        Initialize DAG cache / 初始化 DAG 缓存。

        Args:
            max_cache_size: Maximum number of cached DAG results / 最大缓存 DAG 结果数量
        """
        self.max_cache_size = max_cache_size
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._dag_hashes: Dict[str, str] = {}  # dag_id -> hash
        self._cache_order: List[str] = []  # LRU order tracking

    def has_valid_cache(self, dag_hash: str) -> bool:
        """
        Check if a valid cache exists for the given DAG hash.
        检查给定 DAG 哈希是否存在有效缓存。

        Args:
            dag_hash: SHA256 hash of the DAG structure / DAG 结构的 SHA256 哈希值

        Returns:
            True if cache exists and is valid / 如果缓存存在且有效返回 True
        """
        return dag_hash in self._cache

    def get(self, dag_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get cached execution results for a DAG hash.
        获取 DAG 哈希对应的缓存执行结果。

        Args:
            dag_hash: SHA256 hash of the DAG structure / DAG 结构的 SHA256 哈希值

        Returns:
            Cached results if found, None otherwise / 找到则返回缓存结果，否则返回 None
        """
        if dag_hash in self._cache:
            # Update LRU order
            if dag_hash in self._cache_order:
                self._cache_order.remove(dag_hash)
            self._cache_order.append(dag_hash)
            return self._cache[dag_hash]
        return None

    def set(self, dag_hash: str, results: Dict[str, Any], analyzer: Optional[DependencyAnalyzer] = None) -> None:
        """
        Cache execution results for a DAG hash.
        缓存 DAG 哈希的执行结果。

        Args:
            dag_hash: SHA256 hash of the DAG structure / DAG 结构的 SHA256 哈希值
            results: Execution results to cache / 要缓存的执行结果
            analyzer: Optional DependencyAnalyzer for metadata / 可选的依赖分析器用于元数据
        """
        # Evict oldest if at capacity
        if len(self._cache) >= self.max_cache_size and dag_hash not in self._cache:
            oldest = self._cache_order.pop(0)
            del self._cache[oldest]
            if oldest in self._dag_hashes:
                del self._dag_hashes[oldest]

        self._cache[dag_hash] = results
        if dag_hash not in self._cache_order:
            self._cache_order.append(dag_hash)

    def invalidate(self, dag_hash: str) -> None:
        """
        Invalidate cache for a specific DAG hash.
        使特定 DAG 哈希的缓存失效。

        Args:
            dag_hash: SHA256 hash of the DAG structure / DAG 结构的 SHA256 哈希值
        """
        if dag_hash in self._cache:
            del self._cache[dag_hash]
            if dag_hash in self._cache_order:
                self._cache_order.remove(dag_hash)

    def clear(self) -> None:
        """Clear all cached results / 清除所有缓存结果"""
        self._cache.clear()
        self._dag_hashes.clear()
        self._cache_order.clear()

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics / 获取缓存统计信息。

        Returns:
            Dict with cache statistics / 包含缓存统计的字典
        """
        return {
            "cache_size": len(self._cache),
            "max_cache_size": self.max_cache_size,
            "cache_keys": list(self._cache.keys()),
        }

    def detect_changes(self, analyzer: DependencyAnalyzer, dag_id: str = "default") -> bool:
        """
        Detect if DAG structure has changed since last cache.
        检测 DAG 结构自上次缓存后是否发生变更。

        Args:
            analyzer: DependencyAnalyzer instance / 依赖分析器实例
            dag_id: Identifier for this DAG (for tracking multiple DAGs) / 此 DAG 的标识符

        Returns:
            True if DAG has changed or no cache exists / 如果 DAG 已变更或不存在缓存返回 True
        """
        current_hash = analyzer.compute_dag_hash()
        stored_hash = self._dag_hashes.get(dag_id)

        if stored_hash is None:
            # No previous cache
            self._dag_hashes[dag_id] = current_hash
            return True

        if stored_hash != current_hash:
            # DAG structure changed
            self._dag_hashes[dag_id] = current_hash
            self.invalidate(stored_hash)
            return True

        # No change
        return False
