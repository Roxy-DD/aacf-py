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

from aacf.compiler import AtomicScheduler, DependencyAnalyzer, NodeStatus


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
        NodeStatus.PENDING: "#FFA500",  # Orange / 橙色
        NodeStatus.RUNNING: "#1E90FF",  # Blue / 蓝色
        NodeStatus.DONE: "#32CD32",  # Green / 绿色
        NodeStatus.FAILED: "#FF4500",  # Red / 红色
        NodeStatus.SKIPPED: "#808080",  # Gray / 灰色
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
            raise ValueError("Either app or analyzer must be provided\n必须提供 app 或 analyzer")

    def _get_node_status(self, node_name: str) -> NodeStatus:
        """
        Get the execution status of a node.
        获取节点的执行状态。

        Args:
            node_name: Node name / 节点名

        Returns:
            NodeStatus enum value / NodeStatus 枚举值
        """
        if self.scheduler and node_name in self.scheduler.nodes:
            return self.scheduler.nodes[node_name].status
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
        if self.scheduler and node_name in self.scheduler._results:
            return self.scheduler._results[node_name]
        if self.app and node_name in self.app._compiler.nodes:
            return self.app._compiler.nodes[node_name].result
        return None

    def _build_tooltip_html(self, node_name: str) -> str:
        """
        Build HTML tooltip content for a node with proper line breaks.
        为节点构建带正确换行的 HTML 工具提示内容。

        Args:
            node_name: Node name / 节点名

        Returns:
            HTML string with <br> line breaks / 带 <br> 换行的 HTML 字符串
        """
        status = self._get_node_status(node_name)
        result = self._get_node_result(node_name)

        parts = []
        parts.append(f"<b>Node / 节点:</b> {html.escape(node_name)}")

        if self.show_status:
            parts.append(f"<b>Status / 状态:</b> {html.escape(status.value)}")

        # DSL metadata / DSL 元数据
        if self.app and node_name in self.app._wrappers:
            wrapper = self.app._wrappers[node_name]
            meta = wrapper.__aacf_meta__
            if meta.get("who"):
                parts.append(f"<b>Who / 角色:</b> {html.escape(meta['who'])}")
            if meta.get("what"):
                parts.append(f"<b>What / 任务:</b> {html.escape(meta['what'])}")
            if meta.get("where"):
                parts.append(f"<b>Where / 环境:</b> {html.escape(meta['where'])}")

        if self.show_results and result is not None:
            result_str = str(result)
            if len(result_str) > 200:
                result_str = result_str[:200] + "..."
            parts.append(f"<b>Result / 结果:</b> {html.escape(result_str)}")

        # Use <br> for HTML line breaks / 使用 <br> 实现 HTML 换行
        return "<br>".join(parts)

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
        # Build tooltip map for all nodes / 构建所有节点的工具提示映射
        tooltip_map = {}
        for node_name in self.analyzer.nodes:
            tooltip_map[node_name] = self._build_tooltip_html(node_name)

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

        # Add nodes (title is a placeholder; real tooltip rendered via JS events)
        # 添加节点（title 为占位符；真实工具提示通过 JS 事件渲染）
        for node_name in self.analyzer.nodes:
            status = self._get_node_status(node_name)
            color = self.STATUS_COLORS.get(status, "#FFA500") if self.show_status else "#FFA500"
            shape = self.STATUS_SHAPES.get(status, "dot")

            net.add_node(
                node_name,
                label=node_name,
                title="",  # Empty to disable vis.js native tooltip; custom HTML tooltip used instead / 空字符串禁用 vis.js 原生工具提示；使用自定义 HTML 工具提示
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
                        net.add_edge(
                            dep_name,
                            node_name,
                            color="#848484",
                            width=2,
                            arrows="to",
                            smooth={"type": "continuous"},
                        )

        # Generate base HTML / 生成基础 HTML
        net.write_html(output_path)

        # Post-process: inject custom HTML tooltip system
        # 后处理：注入自定义 HTML 工具提示系统
        self._inject_tooltip_system(output_path, tooltip_map)

        return output_path

    def _inject_tooltip_system(self, output_path: str, tooltip_map: Dict[str, str]) -> None:
        """
        Inject custom HTML tooltip system into the generated HTML file.
        Replaces vis.js native tooltip with a custom HTML-rendered tooltip
        using hoverNode/blurNode events.
        将自定义 HTML 工具提示系统注入到生成的 HTML 文件中。
        使用 hoverNode/blurNode 事件替换 vis.js 原生工具提示为自定义 HTML 渲染的工具提示。
        """
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Build JS tooltip data object / 构建 JS 工具提示数据对象
        # Note: tooltip HTML is intentionally NOT html-escaped here because
        # it will be set via innerHTML (not textContent) for proper rendering.
        # 注意：这里故意不对 tooltip HTML 做 html.escape，因为它将通过
        # innerHTML（而非 textContent）设置以正确渲染 HTML 标签。
        tooltip_js_parts = []
        for node_name, tooltip_html in tooltip_map.items():
            # Only escape JS-special chars (backslash, single quote, newlines)
            # 仅转义 JS 特殊字符（反斜杠、单引号、换行符）
            safe_html = tooltip_html.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
            tooltip_js_parts.append(f"  '{node_name}': '{safe_html}'")
        tooltip_data = "{\n" + ",\n".join(tooltip_js_parts) + "\n}"

        # Custom tooltip JS: create a floating div, show on hoverNode, hide on blurNode
        # 自定义工具提示 JS：创建浮动 div，hoverNode 时显示，blurNode 时隐藏
        custom_js = f"""
        // AACF: Custom HTML tooltip system / 自定义 HTML 工具提示系统
        (function() {{
            // Hide vis.js native tooltip / 隐藏 vis.js 原生工具提示
            var style = document.createElement('style');
            style.textContent = '.vis-tooltip {{ display: none !important; }}';
            document.head.appendChild(style);

            var tooltipDiv = document.createElement('div');
            tooltipDiv.id = 'aacf-tooltip';
            tooltipDiv.style.cssText = 'position:fixed;display:none;background:#fff;border:1px solid #ccc;border-radius:6px;padding:10px 14px;box-shadow:0 2px 8px rgba(0,0,0,0.15);z-index:9999;pointer-events:none;max-width:360px;font-family:arial,sans-serif;';
            document.body.appendChild(tooltipDiv);

            var tooltipData = {tooltip_data};

            network.on('hoverNode', function(params) {{
                var nodeId = params.node;
                if (tooltipData[nodeId]) {{
                    tooltipDiv.innerHTML = tooltipData[nodeId];
                    tooltipDiv.style.display = 'block';
                }}
            }});

            network.on('blurNode', function(params) {{
                tooltipDiv.style.display = 'none';
            }});

            network.on('dragging', function() {{
                tooltipDiv.style.display = 'none';
            }});

            document.addEventListener('mousemove', function(e) {{
                if (tooltipDiv.style.display === 'block') {{
                    var x = e.clientX + 15;
                    var y = e.clientY + 15;
                    // Keep tooltip within viewport / 保持工具提示在视口内
                    var rect = tooltipDiv.getBoundingClientRect();
                    if (x + rect.width > window.innerWidth) x = e.clientX - rect.width - 10;
                    if (y + rect.height > window.innerHeight) y = e.clientY - rect.height - 10;
                    tooltipDiv.style.left = x + 'px';
                    tooltipDiv.style.top = y + 'px';
                }}
            }});
        }})();
        """

        # Insert before the last </script> tag / 在最后一个 </script> 标签前插入
        last_script_close = content.rfind("</script>")
        if last_script_close != -1:
            content = content[:last_script_close] + custom_js + content[last_script_close:]

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

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
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            temp_path = f.name

        try:
            self.generate_html(temp_path)
            with open(temp_path, "r", encoding="utf-8") as f:
                return f.read()
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
