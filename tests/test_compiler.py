# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 AACF Contributors
"""
Tests for compiler module (DependencyAnalyzer, ExecutionPlanner, AtomicNode, AtomicScheduler)
编译器模块测试（依赖分析、执行计划、原子节点、原子调度器）
"""
import pytest
from aacf.compiler import (
    DependencyAnalyzer,
    ExecutionPlanner,
    NodeStatus,
    AtomicNode,
    AtomicNodeConfig,
    AtomicScheduler,
)


# ─── DependencyAnalyzer 测试 ───


class TestDependencyAnalyzer:
    """依赖分析器测试"""

    def test_register_node(self):
        """测试节点注册"""
        analyzer = DependencyAnalyzer()
        analyzer.register_node("a", params=["x"], return_type="str")
        assert "a" in analyzer.nodes
        assert analyzer.nodes["a"].params == ["x"]
        assert analyzer.nodes["a"].return_type == "str"

    def test_register_node_auto_extract_params(self):
        """测试从函数自动提取参数"""
        def my_func(text: str, count: int) -> str:
            pass

        analyzer = DependencyAnalyzer()
        analyzer.register_node("my_func", func=my_func)
        assert analyzer.nodes["my_func"].params == ["text", "count"]

    def test_analyze_no_dependencies(self):
        """测试无依赖关系的节点"""
        analyzer = DependencyAnalyzer()
        analyzer.register_node("a", params=["x"])
        analyzer.register_node("b", params=["y"])
        analyzer.analyze()

        assert analyzer.nodes["a"].dependencies == set()
        assert analyzer.nodes["b"].dependencies == set()

    def test_analyze_with_dependency(self):
        """测试有依赖关系的节点（参数名匹配节点名）"""
        analyzer = DependencyAnalyzer()
        analyzer.register_node("extractor", params=["text"])
        analyzer.register_node("summarizer", params=["extractor"])
        analyzer.analyze()

        assert "extractor" in analyzer.nodes["summarizer"].dependencies
        assert "summarizer" in analyzer.nodes["extractor"].dependents

    def test_analyze_chain_dependency(self):
        """测试链式依赖 A -> B -> C"""
        analyzer = DependencyAnalyzer()
        analyzer.register_node("a", params=["input"])
        analyzer.register_node("b", params=["a"])
        analyzer.register_node("c", params=["b"])
        analyzer.analyze()

        assert "a" in analyzer.nodes["b"].dependencies
        assert "b" in analyzer.nodes["c"].dependencies

    def test_get_execution_order(self):
        """测试拓扑执行顺序"""
        analyzer = DependencyAnalyzer()
        analyzer.register_node("c", params=["b"])
        analyzer.register_node("a", params=["input"])
        analyzer.register_node("b", params=["a"])
        order = analyzer.get_execution_order()

        assert order.index("a") < order.index("b")
        assert order.index("b") < order.index("c")

    def test_get_execution_order_parallel(self):
        """测试并行节点的执行顺序"""
        analyzer = DependencyAnalyzer()
        analyzer.register_node("root", params=["input"])
        analyzer.register_node("left", params=["root"])
        analyzer.register_node("right", params=["root"])
        analyzer.register_node("merge", params=["left", "right"])
        order = analyzer.get_execution_order()

        assert order.index("root") < order.index("left")
        assert order.index("root") < order.index("right")
        assert order.index("left") < order.index("merge")
        assert order.index("right") < order.index("merge")

    def test_circular_dependency_raises(self):
        """测试循环依赖抛出异常"""
        from aacf.compiler import CircularDependencyError
        analyzer = DependencyAnalyzer()
        analyzer.register_node("a", params=["b"])
        analyzer.register_node("b", params=["a"])

        with pytest.raises(CircularDependencyError, match="Circular dependency"):
            analyzer.get_execution_order()

    def test_get_parallel_groups(self):
        """测试并行分组"""
        analyzer = DependencyAnalyzer()
        analyzer.register_node("a", params=["input"])
        analyzer.register_node("b", params=["input"])
        analyzer.register_node("c", params=["a", "b"])
        groups = analyzer.get_parallel_groups()

        # a 和 b 无依赖，应在同一组
        assert len(groups) == 2
        assert sorted(groups[0]) == ["a", "b"]
        assert groups[1] == ["c"]

    def test_get_dependency_graph(self):
        """测试依赖图"""
        analyzer = DependencyAnalyzer()
        analyzer.register_node("a", params=["input"])
        analyzer.register_node("b", params=["a"])
        analyzer.analyze()

        graph = analyzer.get_dependency_graph()
        assert graph["a"] == set()
        assert graph["b"] == {"a"}

    def test_validate_dag_valid(self):
        """测试有效 DAG 验证"""
        analyzer = DependencyAnalyzer()
        analyzer.register_node("a", params=["x"])
        analyzer.register_node("b", params=["a"])
        assert analyzer.validate_dag() is True

    def test_validate_dag_invalid(self):
        """测试无效 DAG（循环）验证"""
        analyzer = DependencyAnalyzer()
        analyzer.register_node("a", params=["b"])
        analyzer.register_node("b", params=["a"])
        assert analyzer.validate_dag() is False


# ─── ExecutionPlanner 测试 ───


class TestExecutionPlanner:
    """执行计划器测试"""

    def _make_analyzer(self):
        analyzer = DependencyAnalyzer()
        analyzer.register_node("a", params=["input"])
        analyzer.register_node("b", params=["a"])
        analyzer.register_node("c", params=["b"])
        analyzer.analyze()
        return analyzer

    def test_create_plan(self):
        """测试创建执行计划"""
        planner = ExecutionPlanner(self._make_analyzer())
        plan = planner.create_plan()

        assert len(plan) == 3
        names = [step["name"] for step in plan]
        assert names.index("a") < names.index("b")
        assert names.index("b") < names.index("c")

    def test_get_next_ready(self):
        """测试获取就绪节点"""
        planner = ExecutionPlanner(self._make_analyzer())
        planner.create_plan()

        ready = planner.get_next_ready()
        assert ready == ["a"]

    def test_mark_complete(self):
        """测试标记完成"""
        planner = ExecutionPlanner(self._make_analyzer())
        planner.create_plan()

        planner.mark_complete("a", result="result_a")
        ready = planner.get_next_ready()
        assert ready == ["b"]

    def test_mark_failed(self):
        """测试标记失败"""
        planner = ExecutionPlanner(self._make_analyzer())
        planner.create_plan()

        planner.mark_failed("a")
        step = next(s for s in planner._plan if s["name"] == "a")
        assert step["status"] == NodeStatus.FAILED

    def test_is_complete(self):
        """测试完成检查"""
        planner = ExecutionPlanner(self._make_analyzer())
        planner.create_plan()

        assert planner.is_complete() is False
        planner.mark_complete("a")
        assert planner.is_complete() is False
        planner.mark_complete("b")
        planner.mark_complete("c")
        assert planner.is_complete() is True


# ─── AtomicNode 测试 ───


class TestAtomicNode:
    """原子节点测试"""

    def test_execute_success(self):
        """测试成功执行"""
        node = AtomicNode("test", func=lambda x: x * 2)
        result = node.execute({"x": 5})
        assert result.is_ok()
        assert result.unwrap() == 10
        assert node.status == NodeStatus.DONE

    def test_execute_with_retry(self):
        """测试重试机制"""
        call_count = 0

        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("transient error")
            return "success"

        node = AtomicNode(
            "flaky",
            func=flaky_func,
            config=AtomicNodeConfig(max_retries=3, retry_delay=0.01),
        )
        result = node.execute()
        assert result.is_ok()
        assert result.unwrap() == "success"
        assert call_count == 3

    def test_execute_all_retries_fail(self):
        """测试所有重试都失败"""
        def always_fail():
            raise ValueError("permanent error")

        node = AtomicNode(
            "fail",
            func=always_fail,
            config=AtomicNodeConfig(max_retries=2, retry_delay=0.01),
        )
        result = node.execute()
        assert result.is_err()
        assert node.status == NodeStatus.FAILED
        assert "permanent error" in result.error

    def test_cache_enabled(self):
        """测试缓存功能"""
        call_count = 0

        def counting_func():
            nonlocal call_count
            call_count += 1
            return f"result_{call_count}"

        node = AtomicNode(
            "cached",
            func=counting_func,
            config=AtomicNodeConfig(cache_enabled=True),
        )

        result1 = node.execute()
        assert result1.is_ok()
        assert result1.unwrap() == "result_1"

        result2 = node.execute()
        assert result2.is_ok()
        assert result2.unwrap() == "result_1"  # 缓存命中 / Cache hit
        assert result2.from_cache is True
        assert call_count == 1  # 只调用一次 / Only called once

    def test_cache_force_reexecute(self):
        """测试强制重新执行（忽略缓存）"""
        call_count = 0

        def counting_func():
            nonlocal call_count
            call_count += 1
            return f"result_{call_count}"

        node = AtomicNode(
            "cached",
            func=counting_func,
            config=AtomicNodeConfig(cache_enabled=True),
        )

        node.execute()
        result = node.execute(force=True)
        assert result.is_ok()
        assert result.unwrap() == "result_2"
        assert result.from_cache is False
        assert call_count == 2

    def test_no_func_raises(self):
        """测试未绑定函数时返回失败结果"""
        node = AtomicNode("empty")
        result = node.execute()
        assert result.is_err()
        assert "No function bound" in result.error

    def test_reset(self):
        """测试重置节点"""
        node = AtomicNode("test", func=lambda: "ok")
        node.execute()
        assert node.status == NodeStatus.DONE

        node.reset()
        assert node.status == NodeStatus.PENDING
        assert node.result is None
        assert node.attempts == 0

    def test_skip(self):
        """测试跳过节点"""
        node = AtomicNode("test", func=lambda: "ok")
        node.skip()
        assert node.status == NodeStatus.SKIPPED

    def test_to_dict(self):
        """测试序列化"""
        node = AtomicNode("test", func=lambda: "ok", dependencies={"a", "b"})
        d = node.to_dict()
        assert d["name"] == "test"
        assert d["status"] == "pending"
        assert set(d["dependencies"]) == {"a", "b"}


# ─── AtomicScheduler 测试 ───


class TestAtomicScheduler:
    """原子调度器测试"""

    def test_add_node(self):
        """测试添加节点"""
        scheduler = AtomicScheduler()
        node = scheduler.add_node("test", func=lambda: "ok")
        assert "test" in scheduler.nodes
        assert node.name == "test"

    def test_run_all_no_deps(self):
        """测试无依赖的节点执行"""
        scheduler = AtomicScheduler()
        scheduler.add_node("a", func=lambda: "result_a")
        scheduler.add_node("b", func=lambda: "result_b")

        results = scheduler.run_all()
        assert results["a"] == "result_a"
        assert results["b"] == "result_b"

    def test_run_all_with_deps(self):
        """测试有依赖的节点执行"""
        scheduler = AtomicScheduler()
        scheduler.add_node("a", func=lambda: "result_a")
        scheduler.add_node("b", func=lambda a: f"b_depends_on_{a}", dependencies={"a"})

        results = scheduler.run_all()
        assert results["a"] == "result_a"
        assert results["b"] == "b_depends_on_result_a"

    def test_run_all_with_inputs(self):
        """测试带输入的节点执行"""
        scheduler = AtomicScheduler()
        scheduler.add_node("a", func=lambda x: x * 2)
        scheduler.add_node("b", func=lambda a: a + 10, dependencies={"a"})

        results = scheduler.run_all(inputs={"a": {"x": 5}})
        assert results["a"] == 10
        assert results["b"] == 20

    def test_run_all_chain(self):
        """测试链式依赖执行"""
        scheduler = AtomicScheduler()
        scheduler.add_node("a", func=lambda: 1)
        scheduler.add_node("b", func=lambda a: a + 1, dependencies={"a"})
        scheduler.add_node("c", func=lambda b: b * 10, dependencies={"b"})

        results = scheduler.run_all()
        assert results["a"] == 1
        assert results["b"] == 2
        assert results["c"] == 20

    def test_run_all_failure_blocks(self):
        """测试失败节点阻塞下游"""
        from aacf.compiler import PipelineError
        def fail():
            raise ValueError("boom")

        scheduler = AtomicScheduler()
        scheduler.add_node("a", func=fail, config=AtomicNodeConfig(max_retries=1, retry_delay=0.01))
        scheduler.add_node("b", func=lambda a: a, dependencies={"a"})

        with pytest.raises(PipelineError, match="failed"):
            scheduler.run_all()

    def test_get_ready_nodes(self):
        """测试获取就绪节点"""
        scheduler = AtomicScheduler()
        scheduler.add_node("a", func=lambda: 1)
        scheduler.add_node("b", func=lambda a: a, dependencies={"a"})

        ready = scheduler.get_ready_nodes()
        ready_names = [n.name for n in ready]
        assert "a" in ready_names
        assert "b" not in ready_names

    def test_get_status_summary(self):
        """测试状态摘要"""
        scheduler = AtomicScheduler()
        scheduler.add_node("a", func=lambda: 1)
        scheduler.add_node("b", func=lambda: 2)

        summary = scheduler.get_status_summary()
        assert summary["pending"] == 2

        scheduler.run_all()
        summary = scheduler.get_status_summary()
        assert summary["done"] == 2


class TestAtomicSchedulerParallel:
    """原子调度器并行执行测试"""

    def test_run_parallel_no_deps(self):
        """测试无依赖的并行执行"""
        scheduler = AtomicScheduler()
        scheduler.add_node("a", func=lambda: "result_a")
        scheduler.add_node("b", func=lambda: "result_b")

        results = scheduler.run_parallel()
        assert results["a"] == "result_a"
        assert results["b"] == "result_b"

    def test_run_parallel_with_deps(self):
        """测试有依赖的并行执行"""
        scheduler = AtomicScheduler()
        scheduler.add_node("a", func=lambda: "result_a")
        scheduler.add_node("b", func=lambda a: f"b_depends_on_{a}", dependencies={"a"})

        results = scheduler.run_parallel()
        assert results["a"] == "result_a"
        assert results["b"] == "b_depends_on_result_a"

    def test_run_parallel_diamond(self):
        """测试菱形依赖的并行执行"""
        scheduler = AtomicScheduler()
        scheduler.add_node("root", func=lambda: "root_result")
        scheduler.add_node("left", func=lambda root: f"left_{root}", dependencies={"root"})
        scheduler.add_node("right", func=lambda root: f"right_{root}", dependencies={"root"})
        scheduler.add_node("merge", func=lambda left, right: f"{left}+{right}", dependencies={"left", "right"})

        results = scheduler.run_parallel()
        assert results["root"] == "root_result"
        assert results["left"] == "left_root_result"
        assert results["right"] == "right_root_result"
        assert results["merge"] == "left_root_result+right_root_result"

    def test_run_parallel_with_inputs(self):
        """测试带输入的并行执行"""
        scheduler = AtomicScheduler()
        scheduler.add_node("a", func=lambda x: x * 2)
        scheduler.add_node("b", func=lambda x: x * 3)

        results = scheduler.run_parallel(inputs={"a": {"x": 5}, "b": {"x": 10}})
        assert results["a"] == 10
        assert results["b"] == 30

    def test_run_parallel_max_workers(self):
        """测试限制最大工作线程数"""
        scheduler = AtomicScheduler()
        scheduler.add_node("a", func=lambda: 1)
        scheduler.add_node("b", func=lambda: 2)

        results = scheduler.run_parallel(max_workers=2)
        assert results["a"] == 1
        assert results["b"] == 2
