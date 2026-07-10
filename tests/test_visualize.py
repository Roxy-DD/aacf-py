# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 AACF Contributors
"""
Tests for DAG visualization / DAG 可视化测试
"""

import locale
import os
import tempfile

import pytest

try:
    from aacf import AACF, DAGVisualizer

    PYVIS_AVAILABLE = True
except ImportError:
    PYVIS_AVAILABLE = False

# pyvis write_html uses locale.getpreferredencoding(), fails on Windows GBK
_HTML_GEN_SUPPORTED = PYVIS_AVAILABLE and locale.getpreferredencoding().lower() == "utf-8"


@pytest.mark.skipif(not PYVIS_AVAILABLE, reason="pyvis not installed / pyvis 未安装")
class TestDAGVisualizer:
    """DAG 可视化器测试"""

    def test_visualizer_creation(self):
        """测试可视化器创建"""
        app = AACF("test")

        @app.node("node_a").who("A").what("Task").build()
        def node_a(text: str):
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

    @pytest.mark.skipif(not _HTML_GEN_SUPPORTED, reason="HTML gen not supported on this platform")
    def test_generate_html_file(self):
        """测试生成 HTML 文件"""
        app = AACF("test")

        @app.node("node_a").who("A").what("Task A").build()
        def node_a(text: str):
            return f"result_a: {text}"

        @app.node("node_b").who("B").what("Task B").build()
        def node_b(node_a: str):
            return f"result_b: {node_a}"

        app.compile()
        app.run_pipeline(inputs={"node_a": {"text": "input"}})

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_dag.html")
            visualizer = DAGVisualizer(app)
            generated_path = visualizer.generate_html(output_path)

            assert os.path.exists(generated_path)
            assert generated_path == output_path

            with open(generated_path, "r", encoding="utf-8") as f:
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
        scheduler.run_all()

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

        @app.node("node_a").who("A").what("Task").build()
        def node_a(text: str):
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

    @pytest.mark.skipif(not _HTML_GEN_SUPPORTED, reason="HTML gen not supported on this platform")
    def test_generate_html_string(self):
        """测试生成 HTML 字符串"""
        app = AACF("test")

        @app.node("node_a").who("A").what("Task").build()
        def node_a(text: str):
            return text

        app.compile()

        visualizer = DAGVisualizer(app)
        html_string = visualizer.generate_html_string()

        assert isinstance(html_string, str)
        assert "<html" in html_string.lower()

    def test_visualizer_node_status_colors(self):
        """测试节点状态颜色映射"""
        from aacf import NodeStatus

        app = AACF("test")

        @app.node("node_a").who("A").what("Task").build()
        def node_a(text: str):
            return text

        app.compile()

        visualizer = DAGVisualizer(app)

        assert NodeStatus.PENDING in visualizer.STATUS_COLORS
        assert NodeStatus.RUNNING in visualizer.STATUS_COLORS
        assert NodeStatus.DONE in visualizer.STATUS_COLORS
        assert NodeStatus.FAILED in visualizer.STATUS_COLORS
        assert NodeStatus.SKIPPED in visualizer.STATUS_COLORS

    @pytest.mark.skipif(not _HTML_GEN_SUPPORTED, reason="HTML gen not supported on this platform")
    def test_visualizer_complex_dag(self):
        """测试复杂 DAG 可视化"""
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

        app.compile()
        app.run_pipeline(inputs={"root": {"text": "input"}})

        visualizer = DAGVisualizer(app)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "complex_dag.html")
            generated_path = visualizer.generate_html(output_path)

            assert os.path.exists(generated_path)

            with open(generated_path, "r", encoding="utf-8") as f:
                html_content = f.read()

            assert "root" in html_content
            assert "left" in html_content
            assert "right" in html_content
            assert "merge" in html_content


@pytest.mark.skipif(not PYVIS_AVAILABLE, reason="pyvis not installed / pyvis 未安装")
class TestDAGVisualizerIntegration:
    """DAG 可视化集成测试"""

    @pytest.mark.skipif(not _HTML_GEN_SUPPORTED, reason="HTML gen not supported on this platform")
    def test_visualization_with_execution_results(self):
        """测试带执行结果的可视化"""
        app = AACF("test")

        @app.node("extractor").who("Extractor").what("Extract data").build()
        def extractor(text: str):
            return {"data": text, "length": len(text)}

        @app.node("processor").who("Processor").what("Process data").build()
        def processor(extractor: dict):
            return f"processed: {extractor}"

        app.compile()
        app.run_pipeline(inputs={"extractor": {"text": "hello world"}})

        visualizer = DAGVisualizer(app, show_results=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "execution_dag.html")
            visualizer.generate_html(output_path)

            assert os.path.exists(output_path)

            with open(output_path, "r", encoding="utf-8") as f:
                html_content = f.read()

            assert "extractor" in html_content
            assert "processor" in html_content
