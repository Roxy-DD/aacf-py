# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 AACF Contributors
"""
Tests for AACF decorator and integration / AACF 装饰器与集成测试
"""

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

    def test_node_decorator_chainable_api(self):
        """测试链式调用 API 装饰器"""
        app = AACF("test")

        @app.node("test_node").who("Tester").what("Test task").build()
        def test_node(text: str):
            pass

        assert hasattr(test_node, "__aacf_meta__")
        assert test_node.__aacf_meta__["who"] == "Tester"
        assert test_node.__aacf_meta__["what"] == "Test task"

    def test_node_decorator_all_params(self):
        """测试链式 API 所有参数"""
        app = AACF("test")

        @(
            app.node("full_node")
            .who("Agent")
            .where("Context")
            .what("Task")
            .why("Reason")
            .how("Method")
            .out("JSON")
            .stream(True)
            .format("json")
            .build()
        )
        def full_node(text: str):
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
        """测试链式 API 缓存配置"""
        app = AACF("test")

        @(
            app.node("cached_node")
            .who("Agent")
            .what("Task")
            .cache(enabled=True, ttl=300)
            .retry(max_attempts=5, delay=2.0)
            .timeout(60)
            .build()
        )
        def cached_node(text: str):
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

        @app.node("default_node").who("Agent").what("Task").build()
        def default_node(text: str):
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

        @app.node("branch_a").who("Branch A").what("Task A").build()
        def branch_a(text: str):
            return f"branch_a: {text}"

        @app.node("branch_b").who("Branch B").what("Task B").build()
        def branch_b(text: str):
            return f"branch_b: {text}"

        @app.node("router").who("Router").what("Route").branches({"a": branch_a, "b": branch_b}).build()
        def router(text: str):
            return "a"

        meta = router.__aacf_meta__
        assert "branches" in meta
        assert "a" in meta["branches"]
        assert "b" in meta["branches"]

    def test_node_registered_in_compiler(self):
        """测试节点注册到编译器"""
        app = AACF("test")

        @app.node("node_a").who("A").what("Task A").build()
        def node_a(text: str):
            pass

        @app.node("node_b").who("B").what("Task B").build()
        def node_b(node_a: str):
            pass

        assert "node_a" in app._compiler.nodes
        assert "node_b" in app._compiler.nodes

    def test_dependency_inference(self):
        """测试依赖关系推断"""
        app = AACF("test")

        @app.node("node_a").who("A").what("Task A").build()
        def node_a(text: str):
            pass

        @app.node("node_b").who("B").what("Task B").build()
        def node_b(node_a: str):
            pass

        app.compile()
        deps = app.get_dependency_graph()
        assert "node_a" in deps["node_b"]

    def test_explicit_code_override(self):
        """测试显式代码覆盖"""
        app = AACF("test")

        @app.node("calculator").who("Calculator").what("Calculate").build()
        def calculator(x: int, y: int):
            return x + y

        result = calculator(x=3, y=5)
        assert result == 8

    def test_wrappers_stored(self):
        """测试包装函数存储"""
        app = AACF("test")

        @app.node("node_a").who("A").what("Task").build()
        def node_a(text: str):
            pass

        assert "node_a" in app._wrappers
        assert callable(app._wrappers["node_a"])


class TestAACFCompile:
    """AACF 编译测试"""

    def test_compile_basic(self):
        """测试基本编译"""
        app = AACF("test")

        @app.node("node_a").who("A").what("Task").build()
        def node_a(text: str):
            pass

        planner = app.compile()
        assert planner is not None
        assert app._compiled is True

    def test_get_execution_order(self):
        """测试获取执行顺序"""
        app = AACF("test")

        @app.node("node_a").who("A").what("Task").build()
        def node_a(text: str):
            pass

        @app.node("node_b").who("B").what("Task").build()
        def node_b(node_a: str):
            pass

        order = app.get_execution_order()
        assert order == ["node_a", "node_b"]

    def test_get_parallel_groups(self):
        """测试获取并行分组"""
        app = AACF("test")

        @app.node("root").who("Root").what("Task").build()
        def root(text: str):
            pass

        @app.node("left").who("Left").what("Task").build()
        def left(root: str):
            pass

        @app.node("right").who("Right").what("Task").build()
        def right(root: str):
            pass

        groups = app.get_parallel_groups()
        assert len(groups) == 2
        assert sorted(groups[0]) == ["root"]
        assert sorted(groups[1]) == ["left", "right"]

    def test_get_dependency_graph(self):
        """测试获取依赖图"""
        app = AACF("test")

        @app.node("node_a").who("A").what("Task").build()
        def node_a(text: str):
            pass

        @app.node("node_b").who("B").what("Task").build()
        def node_b(node_a: str):
            pass

        graph = app.get_dependency_graph()
        assert graph["node_a"] == set()
        assert graph["node_b"] == {"node_a"}


class TestAACFPipeline:
    """AACF 管道执行测试"""

    def test_run_pipeline_basic(self):
        """测试基本管道执行"""
        app = AACF("test")

        @app.node("node_a").who("A").what("Task").build()
        def node_a(text: str):
            return f"processed_{text}"

        @app.node("node_b").who("B").what("Task").build()
        def node_b(node_a: str):
            return f"final_{node_a}"

        results = app.run_pipeline(inputs={"node_a": {"text": "input"}})
        assert results["node_a"] == "processed_input"
        assert results["node_b"] == "final_processed_input"

    def test_run_pipeline_parallel(self):
        """测试并行节点管道执行"""
        app = AACF("test")

        @app.node("root").who("Root").what("Task").build()
        def root(text: str):
            return f"root_{text}"

        @app.node("left").who("Left").what("Task").build()
        def left(root: str):
            return f"left_{root}"

        @app.node("right").who("Right").what("Task").build()
        def right(root: str):
            return f"right_{root}"

        @app.node("merge").who("Merge").what("Task").build()
        def merge(left: str, right: str):
            return f"merge_{left}_{right}"

        results = app.run_pipeline(inputs={"root": {"text": "input"}})
        assert results["root"] == "root_input"
        assert results["left"] == "left_root_input"
        assert results["right"] == "right_root_input"
        assert results["merge"] == "merge_left_root_input_right_root_input"

    def test_run_pipeline_with_config(self):
        """测试带配置的管道执行"""
        app = AACF("test")

        @app.node("node_a").who("A").what("Task").cache(enabled=True).build()
        def node_a(text: str):
            return f"processed_{text}"

        @app.node("node_b").who("B").what("Task").build()
        def node_b(node_a: str):
            return f"final_{node_a}"

        results = app.run_pipeline(inputs={"node_a": {"text": "input"}})
        assert results["node_a"] == "processed_input"
        assert results["node_b"] == "final_processed_input"

    def test_node_status_tracking(self):
        """测试节点状态跟踪"""
        app = AACF("test")

        @app.node("node_a").who("A").what("Task").build()
        def node_a(text: str):
            return text

        @app.node("node_b").who("B").what("Task").build()
        def node_b(node_a: str):
            return node_a

        app.compile()
        statuses = app.get_all_node_statuses()
        assert "node_a" in statuses
        assert "node_b" in statuses
        assert statuses["node_a"] == NodeStatus.PENDING
        assert statuses["node_b"] == NodeStatus.PENDING
