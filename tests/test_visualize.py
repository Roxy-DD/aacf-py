# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 AACF Contributors
"""
Tests for DAG visualization / DAG 可视化测试
"""
import pytest
import tempfile
import os
from pathlib import Path

try:
    from aacf import AACF, DAGVisualizer
    PYVIS_AVAILABLE = True
except ImportError:
    PYVIS_AVAILABLE = False


@pytest.mark.skipif(not PYVIS_AVAILABLE, reason="pyvis not installed / pyvis 未安装")
class TestDAGVisualizer:
    """DAG 可视化器测试"""

    def test_visualizer_creation(self):
        """测试可视化器创建"""
        app = AACF("test")

        @app.node(who="A", what="Task")
        def node_a(text: str):
            """
             【AACF 智能节点 / Smart Node】: A
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: 
            """
            """
             【AACF 智能节点 / Smart Node】: A
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: 
            """
            return text

        app.compile()

        visualizer = DAGVisualizer(app)
        assert visualizer is not None
        assert visualizer.app == app

    def test_visualizer_with_analyzer(self):
        """测试使用 analyzer 创建可视化器"""
        from aacf.compiler import DependencyAnalyzer

        analyzer = DependencyAnalyzer()
        analyzer.register_node("a", params=["x"])
        analyzer.register_node("b", params=["a"])
        analyzer.analyze()

        visualizer = DAGVisualizer(analyzer=analyzer)
        assert visualizer.analyzer == analyzer

    def test_generate_html_file(self):
        """测试生成 HTML 文件"""
        app = AACF("test")

        @app.node(who="A", what="Task A")
        def node_a(text: str):
            """
             【AACF 智能节点 / Smart Node】: A
            🎯 核心任务 / Core Task: Task A
             执行环境 / Environment: 
            """
            """
             【AACF 智能节点 / Smart Node】: A
            🎯 核心任务 / Core Task: Task A
             执行环境 / Environment: 
            """
            return f"result_a: {text}"

        @app.node(who="B", what="Task B")
        def node_b(node_a: str):
            """
             【AACF 智能节点 / Smart Node】: B
            🎯 核心任务 / Core Task: Task B
             执行环境 / Environment: 
            """
            """
             【AACF 智能节点 / Smart Node】: B
            🎯 核心任务 / Core Task: Task B
             执行环境 / Environment: 
            """
            return f"result_b: {node_a}"

        app.compile()
        results = app.run_pipeline(inputs={"node_a": {"text": "input"}})

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_dag.html")
            visualizer = DAGVisualizer(app)
            generated_path = visualizer.generate_html(output_path)

            assert os.path.exists(generated_path)
            assert generated_path == output_path

            # Read and verify HTML content / 读取并验证 HTML 内容
            with open(generated_path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            assert "<html" in html_content.lower()
            assert "node_a" in html_content
            assert "node_b" in html_content

    def test_visualizer_with_scheduler(self):
        """测试使用 scheduler 创建可视化器"""
        from aacf.compiler import AtomicScheduler

        scheduler = AtomicScheduler()
        scheduler.add_node("a", func=lambda: "result_a")
        scheduler.add_node("b", func=lambda a: f"b_{a}", dependencies={"a"})

        results = scheduler.run_all()

        from aacf.compiler import DependencyAnalyzer
        analyzer = DependencyAnalyzer()
        analyzer.register_node("a", params=[])
        analyzer.register_node("b", params=["a"])
        analyzer.analyze()

        visualizer = DAGVisualizer(analyzer=analyzer, scheduler=scheduler)
        assert visualizer.scheduler == scheduler

    def test_visualizer_custom_options(self):
        """测试自定义可视化选项"""
        app = AACF("test")

        @app.node(who="A", what="Task")
        def node_a(text: str):
            """
             【AACF 智能节点 / Smart Node】: A
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: 
            """
            """
             【AACF 智能节点 / Smart Node】: A
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: 
            """
            return text

        app.compile()

        visualizer = DAGVisualizer(
            app,
            title="Custom Title",
            show_status=True,
            show_results=True,
            show_dependencies=True,
            width="1200px",
            height="600px",
            directed=True,
        )

        assert visualizer.title == "Custom Title"
        assert visualizer.show_status is True
        assert visualizer.show_results is True
        assert visualizer.width == "1200px"
        assert visualizer.height == "600px"

    def test_generate_html_string(self):
        """测试生成 HTML 字符串"""
        app = AACF("test")

        @app.node(who="A", what="Task")
        def node_a(text: str):
            """
             【AACF 智能节点 / Smart Node】: A
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: 
            """
            """
             【AACF 智能节点 / Smart Node】: A
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: 
            """
            return text

        app.compile()

        visualizer = DAGVisualizer(app)
        html_string = visualizer.generate_html_string()

        assert isinstance(html_string, str)
        assert "<html" in html_string.lower()
        assert "node_a" in html_string

    def test_visualizer_requires_app_or_analyzer(self):
        """测试可视化器需要 app 或 analyzer"""
        with pytest.raises(ValueError, match="Either app or analyzer"):
            DAGVisualizer()

    def test_visualizer_node_status_colors(self):
        """测试节点状态颜色映射"""
        from aacf.compiler import NodeStatus

        app = AACF("test")

        @app.node(who="A", what="Task")
        def node_a(text: str):
            """
             【AACF 智能节点 / Smart Node】: A
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: 
            """
            """
             【AACF 智能节点 / Smart Node】: A
            🎯 核心任务 / Core Task: Task
             执行环境 / Environment: 
            """
            return text

        app.compile()

        visualizer = DAGVisualizer(app)

        # Check color mapping exists / 检查颜色映射存在
        assert NodeStatus.PENDING in visualizer.STATUS_COLORS
        assert NodeStatus.RUNNING in visualizer.STATUS_COLORS
        assert NodeStatus.DONE in visualizer.STATUS_COLORS
        assert NodeStatus.FAILED in visualizer.STATUS_COLORS
        assert NodeStatus.SKIPPED in visualizer.STATUS_COLORS

    def test_visualizer_complex_dag(self):
        """测试复杂 DAG 可视化"""
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

        app.compile()
        results = app.run_pipeline(inputs={"root": {"text": "input"}})

        visualizer = DAGVisualizer(app)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "complex_dag.html")
            generated_path = visualizer.generate_html(output_path)

            assert os.path.exists(generated_path)

            with open(generated_path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            # All nodes should be in HTML / 所有节点都应在 HTML 中
            assert "root" in html_content
            assert "left" in html_content
            assert "right" in html_content
            assert "merge" in html_content


@pytest.mark.skipif(not PYVIS_AVAILABLE, reason="pyvis not installed / pyvis 未安装")
class TestDAGVisualizerIntegration:
    """DAG 可视化集成测试"""

    def test_visualization_with_execution_results(self):
        """测试带执行结果的可视化"""
        app = AACF("test")

        @app.node(who="Extractor", what="Extract data")
        def extractor(text: str):
            """
             【AACF 智能节点 / Smart Node】: Extractor
            🎯 核心任务 / Core Task: Extract data
             执行环境 / Environment: 
            """
            return {"data": text, "length": len(text)}

        @app.node(who="Processor", what="Process data")
        def processor(extractor: dict):
        # Create visualizer with execution context / 创建带执行上下文的可视化器
            visualizer = DAGVisualizer(app, show_results=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "execution_dag.html")
            return text

        @app.node(who="B", what="Task B")
        def node_b(node_a: str):
            return node_a

        @app.node(who="C", what="Task C")
        def node_c(node_b: str):
            """
             【AACF 智能节点 / Smart Node】: C
            🎯 核心任务 / Core Task: Task C
             执行环境 / Environment: 
            """
            return node_b

        app.compile()

        visualizer = DAGVisualizer(app)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "deps_dag.html")
            visualizer.generate_html(output_path)

            with open(output_path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            # Edges should be represented in HTML / 边应在 HTML 中表示
            # pyvis uses JavaScript to draw edges / pyvis 使用 JavaScript 绘制边
            assert "node_a" in html_content
            assert "node_b" in html_content
            assert "node_c" in html_content
