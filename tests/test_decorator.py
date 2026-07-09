# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 AACF Contributors
"""
Tests for AACF decorator and integration / AACF 装饰器与集成测试
"""
import pytest
from aacf import AACF, LLMConfig, NodeStatus


class TestAACFDecorator:
    """AACF 装饰器测试"""

    def test_app_creation(self):
        """测试应用创建"""
        app = AACF("test_app")
        assert app.name == "test_app"
        assert app.config is None

    def test_app_with_config(self):
        """测试带配置的应用创建"""
        config = LLMConfig(model="test-model")
        app = AACF("test_app", config=config)
        assert app.config.get_dict()["model"] == "test-model"

    def test_node_decorator_basic(self):
        """测试基本节点装饰器"""
        app = AACF("test")

        @app.node(who="Tester", what="Test task")
        def test_node(text: str):
            """
             【AACF 智能节点 / Smart Node】: Tester
            🎯 核心任务 / Core Task: Test task
             执行环境 / Environment: 
            """
            pass

        assert hasattr(test_node, "__aacf_meta__")
        assert test_node.__aacf_meta__["who"] == "Tester"
        assert test_node.__aacf_meta__["what"] == "Test task"

    def test_node_decorator_all_params(self):
        """测试装饰器所有参数"""
        app = AACF("test")

        @app.node(
            who="Agent",
            where="Context",
            what="Task",
            why="Reason",
            how="Method",
            out="JSON",
            stream=True,
            format="json",
        )
        def full_node(text: str):
            """
             【AACF 智能节点 / Smart Node】: Agent
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: Context
            """
            pass

        meta = full_node.__aacf_meta__
        assert meta["who"] == "Agent"
        assert meta["where"] == "Context"
        assert meta["what"] == "Task"
        assert meta["why"] == "Reason"
        assert meta["how"] == "Method"
        assert meta["out"] == "JSON"
        assert meta["stream"] is True
        assert meta["format"] == "json"

    def test_node_decorator_cache_config(self):
        """测试装饰器缓存配置参数"""
        app = AACF("test")

        @app.node(
            who="Agent",
            what="Task",
            cache_enabled=True,
            cache_ttl=300,
            max_retries=5,
            retry_delay=2.0,
            timeout=60,
        )
        def cached_node(text: str):
            """
             【AACF 智能节点 / Smart Node】: Agent
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: 
            """
            pass

        meta = cached_node.__aacf_meta__
        assert meta["cache_enabled"] is True
        assert meta["cache_ttl"] == 300
        assert meta["max_retries"] == 5
        assert meta["retry_delay"] == 2.0
        assert meta["timeout"] == 60

    def test_node_decorator_cache_defaults(self):
        """测试装饰器缓存配置默认值"""
        app = AACF("test")

        @app.node(who="Agent", what="Task")
        def default_node(text: str):
            """
             【AACF 智能节点 / Smart Node】: Agent
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: 
            """
            pass

        meta = default_node.__aacf_meta__
        assert meta["cache_enabled"] is False
        assert meta["cache_ttl"] == 0
        assert meta["max_retries"] == 3
        assert meta["retry_delay"] == 1.0
        assert meta["timeout"] == 0

    def test_node_decorator_branches(self):
        """测试装饰器条件分支配置"""
        app = AACF("test")

        @app.node(who="Branch A", what="Task A")
        def branch_a(text: str):
            """
             【AACF 智能节点 / Smart Node】: Branch A
            🎯 核心任务 / Core Task: Task A
             执行环境 / Environment: 
            """
            return f"branch_a: {text}"

        @app.node(who="Branch B", what="Task B")
        def branch_b(text: str):
            """
             【AACF 智能节点 / Smart Node】: Branch B
            🎯 核心任务 / Core Task: Task B
             执行环境 / Environment: 
            """
            return f"branch_b: {text}"

        @app.node(
            who="Router",
            what="Route to branch",
            branches={"a": branch_a, "b": branch_b},
        )
        def router(text: str):
            """
             【AACF 智能节点 / Smart Node】: Router
            🎯 核心任务 / Core Task: Route to branch
             执行环境 / Environment: 
            """
            return "a"  # 返回分支键 / Return branch key

        meta = router.__aacf_meta__
        assert "branches" in meta
        assert meta["branches"] is not None
        assert "a" in meta["branches"]
        assert "b" in meta["branches"]
        assert meta["branches"]["a"] == branch_a
        assert meta["branches"]["b"] == branch_b

    def test_node_registered_in_compiler(self):
        """测试节点注册到编译器"""
        app = AACF("test")

        @app.node(who="A", what="Task A")
        def node_a(text: str):
            """
             【AACF 智能节点 / Smart Node】: A
            🎯 核心任务 / Core Task: Task A
             执行环境 / Environment: 
            """
            pass

        @app.node(who="B", what="Task B")
        def node_b(node_a: str):
            """
             【AACF 智能节点 / Smart Node】: B
            🎯 核心任务 / Core Task: Task B
             执行环境 / Environment: 
            """
            pass

        assert "node_a" in app._compiler.nodes
        assert "node_b" in app._compiler.nodes

    def test_dependency_inference(self):
        """测试依赖关系推断"""
        app = AACF("test")

        @app.node(who="A", what="Task A")
        def node_a(text: str):
            """
             【AACF 智能节点 / Smart Node】: A
            🎯 核心任务 / Core Task: Task A
             执行环境 / Environment: 
            """
            pass

        @app.node(who="B", what="Task B")
        def node_b(node_a: str):
            """
             【AACF 智能节点 / Smart Node】: B
            🎯 核心任务 / Core Task: Task B
             执行环境 / Environment: 
            """
            pass

        app.compile()
        deps = app.get_dependency_graph()
        assert "node_a" in deps["node_b"]

    def test_explicit_code_override(self):
        """测试显式代码覆盖"""
        app = AACF("test")

        @app.node(who="Calculator", what="Calculate")
        def calculator(x: int, y: int):
            """
             【AACF 智能节点 / Smart Node】: Calculator
            🎯 核心任务 / Core Task: Calculate
             执行环境 / Environment: 
            """
            return x + y

        result = calculator(x=3, y=5)
        assert result == 8

    def test_wrappers_stored(self):
        """测试包装函数存储"""
        app = AACF("test")

        @app.node(who="A", what="Task")
        def node_a(text: str):
            """
             【AACF 智能节点 / Smart Node】: A
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: 
            """
            pass

        assert "node_a" in app._wrappers
        assert callable(app._wrappers["node_a"])


class TestAACFCompile:
    """AACF 编译测试"""

    def test_compile_basic(self):
        """测试基本编译"""
        app = AACF("test")

        @app.node(who="A", what="Task")
        def node_a(text: str):
            """
             【AACF 智能节点 / Smart Node】: A
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: 
            """
            pass

        planner = app.compile()
        assert planner is not None
        assert app._compiled is True

    def test_get_execution_order(self):
        """测试获取执行顺序"""
        app = AACF("test")

        @app.node(who="A", what="Task")
        def node_a(text: str):
            """
             【AACF 智能节点 / Smart Node】: A
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: 
            """
            pass

        @app.node(who="B", what="Task")
        def node_b(node_a: str):
            """
             【AACF 智能节点 / Smart Node】: B
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: 
            """
            pass

        order = app.get_execution_order()
        assert order == ["node_a", "node_b"]

    def test_get_parallel_groups(self):
        """测试获取并行分组"""
        app = AACF("test")

        @app.node(who="Root", what="Task")
        def root(text: str):
            """
             【AACF 智能节点 / Smart Node】: Root
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: 
            """
            pass

        @app.node(who="Left", what="Task")
        def left(root: str):
            """
             【AACF 智能节点 / Smart Node】: Left
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: 
            """
            pass

        @app.node(who="Right", what="Task")
        def right(root: str):
            """
             【AACF 智能节点 / Smart Node】: Right
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: 
            """
            pass

        groups = app.get_parallel_groups()
        assert len(groups) == 2
        assert sorted(groups[0]) == ["root"]
        assert sorted(groups[1]) == ["left", "right"]

    def test_get_dependency_graph(self):
        """测试获取依赖图"""
        app = AACF("test")

        @app.node(who="A", what="Task")
        def node_a(text: str):
            """
             【AACF 智能节点 / Smart Node】: A
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: 
            """
            pass

        @app.node(who="B", what="Task")
        def node_b(node_a: str):
            """
             【AACF 智能节点 / Smart Node】: B
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: 
            """
            pass

        graph = app.get_dependency_graph()
        assert graph["node_a"] == set()
        assert graph["node_b"] == {"node_a"}


class TestAACFPipeline:
    """AACF 管道执行测试"""

    def test_run_pipeline_basic(self):
        """测试基本管道执行"""
        app = AACF("test")

        @app.node(who="A", what="Task")
        def node_a(text: str):
            """
             【AACF 智能节点 / Smart Node】: A
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: 
            """
            return f"processed_{text}"

        @app.node(who="B", what="Task")
        def node_b(node_a: str):
            """
             【AACF 智能节点 / Smart Node】: B
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: 
            """
            return f"final_{node_a}"

        results = app.run_pipeline(inputs={"node_a": {"text": "input"}})
        assert results["node_a"] == "processed_input"
        assert results["node_b"] == "final_processed_input"

    def test_run_pipeline_parallel(self):
        """测试并行节点管道执行"""
        app = AACF("test")

        @app.node(who="Root", what="Task")
        def root(text: str):
            """
             【AACF 智能节点 / Smart Node】: Root
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: 
            """
            return f"root_{text}"

        @app.node(who="Left", what="Task")
        def left(root: str):
            """
             【AACF 智能节点 / Smart Node】: Left
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: 
            """
            return f"left_{root}"

        @app.node(who="Right", what="Task")
        def right(root: str):
            """
             【AACF 智能节点 / Smart Node】: Right
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: 
            """
            return f"right_{root}"

        @app.node(who="Merge", what="Task")
        def merge(left: str, right: str):
            """
             【AACF 智能节点 / Smart Node】: Merge
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: 
            """
            return f"merge_{left}_{right}"

        results = app.run_pipeline(inputs={"root": {"text": "input"}})
        assert results["root"] == "root_input"
        assert results["left"] == "left_root_input"
        assert results["right"] == "right_root_input"
        assert results["merge"] == "merge_left_root_input_right_root_input"

    def test_run_pipeline_with_config(self):
        """测试带配置的管道执行"""
        app = AACF("test")

        @app.node(who="A", what="Task", cache_enabled=True)
        def node_a(text: str):
            """
             【AACF 智能节点 / Smart Node】: A
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: 
            """
            return f"processed_{text}"

        @app.node(who="B", what="Task")
        def node_b(node_a: str):
            """
             【AACF 智能节点 / Smart Node】: B
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: 
            """
            return f"final_{node_a}"

        results = app.run_pipeline(inputs={"node_a": {"text": "input"}})
        assert results["node_a"] == "processed_input"
        assert results["node_b"] == "final_processed_input"

    def test_node_status_tracking(self):
        """测试节点状态跟踪"""
        app = AACF("test")

        @app.node(who="A", what="Task")
        def node_a(text: str):
            """
             【AACF 智能节点 / Smart Node】: A
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: 
            """
            return text

        @app.node(who="B", what="Task")
        def node_b(node_a: str):
            """
             【AACF 智能节点 / Smart Node】: B
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: 
            """
            return node_a

        app.compile()
        statuses = app.get_all_node_statuses()
        assert "node_a" in statuses
        assert "node_b" in statuses
        assert statuses["node_a"] == NodeStatus.PENDING
        assert statuses["node_b"] == NodeStatus.PENDING
