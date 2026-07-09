# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 AACF Contributors
"""
AACF Visualizer — Interactive HTML DAG visualization using pyvis.
AACF 可视化器 — 使用 pyvis 的交互式 HTML DAG 可视化。

This module provides:
- DAGVisualizer: Generate interactive HTML visualization of DAG structure
- Node status display with color-coded states
- Dependency edges with direction indicators
- Execution result annotations

本模块提供：
- DAGVisualizer：生成 DAG 结构的交互式 HTML 可视化
- 节点状态显示，使用颜色编码状态
- 带方向指示器的依赖边
- 执行结果标注

Usage::

    from aacf import AACF, DAGVisualizer

    app = AACF(__name__)
    # ... register nodes ...
    app.compile()

    visualizer = DAGVisualizer(app)
    visualizer.generate_html("dag.html")
"""
import html
from typing import Any, Dict, Optional

try:
    from pyvis.network import Network
    PYVIS_AVAILABLE = True
except ImportError:
    PYVIS_AVAILABLE = False

from aacf.compiler import NodeStatus, DependencyAnalyzer, AtomicScheduler


class DAGVisualizer:
    """
    Interactive HTML visualization for AACF DAGs.
    AACF DAG 的交互式 HTML 可视化。

    Generates a standalone HTML file with an interactive DAG visualization
    using the pyvis library. Nodes are color-coded by execution status,
    and edges show dependency relationships.

    使用 pyvis 库生成包含交互式 DAG 可视化的独立 HTML 文件。
    节点按执行状态进行颜色编码，边显示依赖关系。

    Usage::

        visualizer = DAGVisualizer(app)
        visualizer.generate_html("output.html")

        # Or with custom options / 或使用自定义选项
        visualizer = DAGVisualizer(
            app,
            title="My Pipeline",
            show_status=True,
            show_results=True,
        )
        visualizer.generate_html("output.html")
    """

    # Node status color mapping / 节点状态颜色映射
    STATUS_COLORS = {
        NodeStatus.PENDING: "#FFA500",      # Orange / 橙色
        NodeStatus.RUNNING: "#1E90FF",      # Blue / 蓝色
        NodeStatus.DONE: "#32CD32",         # Green / 绿色
        NodeStatus.FAILED: "#FF4500",       # Red / 红色
        NodeStatus.SKIPPED: "#808080",      # Gray / 灰色
    }

    # Node status shapes / 节点状态形状
    STATUS_SHAPES = {
        NodeStatus.PENDING: "dot",
        NodeStatus.RUNNING: "diamond",
        NodeStatus.DONE: "dot",
        NodeStatus.FAILED: "triangle",
        NodeStatus.SKIPPED: "square",
    }

    def __init__(
        self,
        app=None,
        analyzer: Optional[DependencyAnalyzer] = None,
        scheduler: Optional[AtomicScheduler] = None,
        title: str = "AACF DAG Visualization",
        show_status: bool = True,
        show_results: bool = True,
        show_dependencies: bool = True,
        width: str = "100%",
        height: str = "800px",
        directed: bool = True,
    ):
        """
        Initialize the DAG visualizer.
        初始化 DAG 可视化器。

        Args:
            app: AACF application instance / AACF 应用实例
            analyzer: DependencyAnalyzer instance (alternative to app) /
                      DependencyAnalyzer 实例（替代 app）
            scheduler: AtomicScheduler instance with execution results /
                       包含执行结果的 AtomicScheduler 实例
            title: HTML page title / HTML 页面标题
            show_status: Whether to color nodes by status / 是否按状态为节点着色
            show_results: Whether to show execution results in tooltips /
                          是否在工具提示中显示执行结果
            show_dependencies: Whether to show dependency edges / 是否显示依赖边
            width: Visualization width / 可视化宽度
            height: Visualization height / 可视化高度
            directed: Whether edges should be directed (arrows) / 边是否应有方向（箭头）
        """
        if not PYVIS_AVAILABLE:
            raise ImportError(
                "pyvis is required for visualization. Install with: pip install pyvis\n"
                "可视化需要 pyvis。请使用以下命令安装：pip install pyvis"
            )

        self.app = app
        self.analyzer = analyzer or (app._compiler if app else None)
        self.scheduler = scheduler
        self.title = title
        self.show_status = show_status
        self.show_results = show_results
        self.show_dependencies = show_dependencies
        self.width = width
        self.height = height
        self.directed = directed

        if self.analyzer is None:
            raise ValueError(
                "Either app or analyzer must be provided\n"
                "必须提供 app 或 analyzer"
            )

    def _get_node_status(self, node_name: str) -> NodeStatus:
        """
        Get the execution status of a node.
        获取节点的执行状态。

        Args:
            node_name: Node name / 节点名

        Returns:
            NodeStatus enum value / NodeStatus 枚举值
        """
        # Check scheduler first (has most recent status) / 首先检查调度器（有最新状态）
        if self.scheduler and node_name in self.scheduler.nodes:
            return self.scheduler.nodes[node_name].status

        # Then check app compiler / 然后检查应用编译器
        if self.app and node_name in self.app._compiler.nodes:
            return self.app._compiler.nodes[node_name].status

        return NodeStatus.PENDING

    def _get_node_result(self, node_name: str) -> Optional[Any]:
        """
        Get the execution result of a node.
        获取节点的执行结果。

        Args:
            node_name: Node name / 节点名

        Returns:
            Execution result or None / 执行结果或 None
        """
        # Check scheduler first / 首先检查调度器
        if self.scheduler and node_name in self.scheduler._results:
            return self.scheduler._results[node_name]

        # Then check app compiler / 然后检查应用编译器
        if self.app and node_name in self.app._compiler.nodes:
            return self.app._compiler.nodes[node_name].result

        return None

    def _format_result(self, result: Any) -> str:
        """
        Format execution result for display.
        格式化执行结果以用于显示。

        Args:
            result: Execution result / 执行结果

        Returns:
            Formatted string / 格式化字符串
        """
        if result is None:
            return "No result / 无结果"

        # Truncate long results / 截断长结果
        result_str = str(result)
        if len(result_str) > 200:
            result_str = result_str[:200] + "..."

        # Escape HTML / 转义 HTML
        return html.escape(result_str)

    def generate_html(self, output_path: str = "dag.html") -> str:
        """
        Generate interactive HTML visualization.
        生成交互式 HTML 可视化。

        Args:
            output_path: Output HTML file path / 输出 HTML 文件路径

        Returns:
            Path to generated HTML file / 生成的 HTML 文件路径

        Example::

            visualizer = DAGVisualizer(app)
            html_path = visualizer.generate_html("pipeline.html")
            print(f"Visualization saved to: {html_path}")
        """
        # Create pyvis network / 创建 pyvis 网络
        net = Network(
            width=self.width,
            height=self.height,
            directed=self.directed,
            notebook=False,
            cdn_resources="in_line",
        )

        # Set physics options for better layout / 设置物理选项以获得更好的布局
        net.set_options("""
        {
            "physics": {
                "enabled": true,
                "barnesHut": {
                    "gravitationalConstant": -2000,
                    "centralGravity": 0.3,
                    "springLength": 150,
                    "springConstant": 0.04,
                    "damping": 0.09
                }
            },
            "interaction": {
                "hover": true,
                "tooltipDelay": 200
            }
        }
        """)

        # Add nodes / 添加节点
        for node_name, node_info in self.analyzer.nodes.items():
            status = self._get_node_status(node_name)
            result = self._get_node_result(node_name)

            # Build tooltip / 构建工具提示
            tooltip_parts = [f"<b>Node / 节点:</b> {html.escape(node_name)}"]

            if self.show_status:
                tooltip_parts.append(f"<b>Status / 状态:</b> {status.value}")

            # Add DSL metadata if available / 添加 DSL 元数据（如果可用）
            if self.app and node_name in self.app._wrappers:
                wrapper = self.app._wrappers[node_name]
                meta = wrapper.__aacf_meta__
                if meta.get("who"):
                    tooltip_parts.append(f"<b>Who / 角色:</b> {html.escape(meta['who'])}")
                if meta.get("what"):
                    tooltip_parts.append(f"<b>What / 任务:</b> {html.escape(meta['what'])}")
                if meta.get("where"):
                    tooltip_parts.append(f"<b>Where / 环境:</b> {html.escape(meta['where'])}")

            if self.show_results and result is not None:
                tooltip_parts.append(f"<b>Result / 结果:</b><br>{self._format_result(result)}")

            tooltip = "<br>".join(tooltip_parts)

            # Determine node appearance / 确定节点外观
            color = self.STATUS_COLORS.get(status, "#FFA500") if self.show_status else "#FFA500"
            shape = self.STATUS_SHAPES.get(status, "dot")

            # Add node to network / 向网络添加节点
            net.add_node(
                node_name,
                label=node_name,
                title=tooltip,
                color=color,
                shape=shape,
                size=25,
                font={"size": 14, "color": "#000000", "face": "arial"},
                borderWidth=2,
                borderHighlight=True,
            )

        # Add edges for dependencies / 为依赖添加边
        if self.show_dependencies:
            for node_name, node_info in self.analyzer.nodes.items():
                for dep_name in node_info.dependencies:
                    if dep_name in self.analyzer.nodes:
                        # Edge from dependency to dependent / 从依赖到依赖者的边
                        net.add_edge(
                            dep_name,
                            node_name,
                            color="#848484",
                            width=2,
                            arrows="to",
                            smooth={"type": "continuous"},
                        )

        # Generate HTML / 生成 HTML
        net.write_html(output_path)

        return output_path

    def generate_html_string(self) -> str:
        """
        Generate HTML as a string instead of writing to file.
        生成 HTML 字符串而不是写入文件。

        Returns:
            HTML content as string / HTML 内容字符串

        Example::

            visualizer = DAGVisualizer(app)
            html_content = visualizer.generate_html_string()
            # Embed in web page / 嵌入网页
        """
        import tempfile
        import os

        # Create temporary file / 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            temp_path = f.name

        try:
            self.generate_html(temp_path)
            with open(temp_path, 'r', encoding='utf-8') as f:
                return f.read()
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
