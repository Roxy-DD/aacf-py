# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 AACF Contributors
"""
MCP Tools: Project Management / 项目管理工具。

Tools for initializing, reading, and validating AACF projects.
初始化、读取和验证 AACF 项目的工具。
"""

import subprocess
import sys
from pathlib import Path

from mcp.types import ToolAnnotations


def register_project_tools(mcp):
    """Register all project management tools with the MCP server."""

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Initialize Project",
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
    )
    def init_project(project_name: str, path: str = "", create_venv: bool = False) -> dict:
        """
        Initialize a new AACF project with standard structure.
        初始化具有标准结构的新 AACF 项目。

        Creates:
        - agents.py: Node definitions / 节点定义
        - main.py: Entry point / 入口文件
        - README.md: Project documentation / 项目文档
        - .venv/: Virtual environment with aacf installed (optional) / 虚拟环境（可选）

        Args:
            project_name: Name of the new project directory
            path: Parent directory path (default: current directory)
            create_venv: Create virtual environment and install aacf (default: False)
        """
        parent = Path(path).resolve() if path else Path.cwd()
        project_dir = parent / project_name

        if project_dir.exists():
            return {"error": f"Directory '{project_name}' already exists at {parent}."}

        # Create project directory
        project_dir.mkdir(parents=True)

        # Create agents.py
        agents_content = '''# SPDX-License-Identifier: GPL-3.0
"""AI agent node definitions / AI 智能体节点定义。

Use the chainable API to configure nodes:
使用链式 API 配置节点：

    @app.node("name").who("role").what("task")
    def my_node(param: str):
        pass

Available chain methods / 可用链式方法：
    .who(role)        - Agent role / 智能体角色
    .what(task)       - Core task / 核心任务
    .where(context)   - Business context / 业务环境
    .why(reason)      - Execution intent / 执行意图
    .how(method)      - Operation method / 操作方法
    .stream(True)     - Enable streaming / 启用流式输出
    .format("json")   - JSON output / JSON 输出
    .out(requirement) - Output format / 输出格式要求
    .cache(ttl=300)   - Enable cache / 启用缓存
    .retry(max_attempts=3, delay=1.0) - Retry config / 重试配置
    .timeout(seconds) - Timeout config / 超时配置
"""

from aacf import AACF, LLMConfig

# ── Initialize App / 初始化应用 ──────────────────────────────────────
app = AACF(
    __name__,
    config=LLMConfig(
        model="qwen2.5-7b-instruct",
        url="http://127.0.0.1:8080/v1/chat/completions",
        language="zh",  # "zh" (中文) or "en" (English)
    ),
)


# ── Node Definitions / 节点定义 ──────────────────────────────────────


@app.node("greeting").who("友好助手").what("向用户打招呼并回答问题")
def greeting(name: str):
    """A simple greeting node. / 简单的问候节点。"""
    pass


@app.node("summary").who("摘要专家").what("根据输入内容生成简洁摘要").cache(ttl=300)
def summary(greeting: str):
    """A summary node that depends on greeting (param name matches upstream node).
    摘要节点，依赖 greeting（参数名匹配上游节点名）。"""
    pass
'''
        (project_dir / "agents.py").write_text(agents_content, encoding="utf-8")

        # Create main.py
        main_content = '''# SPDX-License-Identifier: GPL-3.0
"""Application entry point / 应用入口文件。

Demonstrates:
  1. Calling individual nodes / 调用单个节点
  2. Pipeline execution with dependency analysis / 带依赖分析的管道执行
"""

from agents import app, greeting, summary


if __name__ == "__main__":
    # 1. Call a single node / 调用单个节点
    print("=== Node Call / 节点调用 ===")
    print(greeting(name="World"))
    print()

    # 2. Run pipeline (auto-resolves dependencies) / 运行管道（自动解析依赖）
    print("=== Pipeline / 管道执行 ===")
    results = app.run_pipeline(inputs={"greeting": {"name": "AACF"}})
    for node_name, result in results.items():
        print(f"{node_name}: {result}")
'''
        (project_dir / "main.py").write_text(main_content, encoding="utf-8")

        # Create README.md
        readme_content = f"""# {project_name}

An AACF-powered AI agent project.

## Project Structure / 项目结构

```
{project_name}/
├── agents.py    # Node definitions (chainable API) / 节点定义（链式 API）
├── main.py      # Entry point / 入口文件
├── README.md    # This file / 本文件
└── .gitignore
```

## Quick Start / 快速开始

```bash
# Install dependencies / 安装依赖
pip install aacf

# Run the project / 运行项目
python main.py
```

## Node Configuration / 节点配置

Use the chainable API to configure nodes in `agents.py`:
在 `agents.py` 中使用链式 API 配置节点：

```python
@app.node("name")           # Node name / 节点名称
    .who("role")            # Agent role / 智能体角色
    .what("task")           # Core task / 核心任务
    .where("context")       # Business context / 业务环境
    .stream(True)           # Streaming output / 流式输出
    .format("json")         # JSON output / JSON 输出
    .cache(ttl=300)         # Cache 5 min / 缓存 5 分钟
    .retry(max_attempts=3)  # Retry config / 重试配置
def my_node(param: str):
    pass
```

## Pipeline / 管道执行

AACF automatically analyzes dependencies between nodes and builds a DAG.
AACF 自动分析节点间的依赖关系并构建 DAG。

```python
# Run pipeline with inputs / 运行管道并传入输入
results = app.run_pipeline(inputs={{"node_name": {{"param": "value"}}}})

# Query execution plan / 查询执行计划
app.get_execution_order()   # Topological order / 拓扑顺序
app.get_parallel_groups()   # Parallel groups / 并行分组
app.get_dependency_graph()  # Dependency graph / 依赖图
```

## Dependency Convention / 依赖约定

Parameter names matching upstream node names create automatic dependencies:
参数名匹配上游节点名时，自动建立依赖关系：

```python
@app.node("extractor").who("提取器").what("提取信息")
def extractor(text: str):
    pass

@app.node("summarizer").who("摘要器").what("生成摘要")
def summarizer(extractor: str):  # param "extractor" -> depends on node "extractor"
    pass                          # 参数名 "extractor" 依赖节点 "extractor"
```

## License / 许可证

SPDX-License-Identifier: GPL-3.0
"""
        (project_dir / "README.md").write_text(readme_content, encoding="utf-8")

        # Create .gitignore
        gitignore_content = """__pycache__/
*.py[cod]
*$py.class
*.so
.Python
.venv/
venv/
ENV/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
"""
        (project_dir / ".gitignore").write_text(gitignore_content, encoding="utf-8")

        # Create .qoder/mcp.json — MCP server config for Qoder
        qoder_dir = project_dir / ".qoder"
        qoder_dir.mkdir(exist_ok=True)
        mcp_json = qoder_dir / "mcp.json"
        mcp_json.write_text(
            "{\n"
            '  "mcpServers": {\n'
            '    "aacf": {\n'
            '      "command": "python",\n'
            '      "args": ["-m", "aacf_mcp"]\n'
            "    }\n"
            "  }\n"
            "}\n",
            encoding="utf-8",
        )

        # Create virtual environment and install aacf (optional)
        venv_created = False
        if create_venv:
            try:
                subprocess.run(
                    [sys.executable, "-m", "venv", ".venv"],
                    cwd=project_dir,
                    check=True,
                    capture_output=True,
                    timeout=30,  # 30 second timeout
                )

                # Determine pip path
                if sys.platform == "win32":
                    pip_path = project_dir / ".venv" / "Scripts" / "pip.exe"
                else:
                    pip_path = project_dir / ".venv" / "bin" / "pip"

                subprocess.run(
                    [str(pip_path), "install", "aacf"],
                    cwd=project_dir,
                    check=True,
                    capture_output=True,
                    timeout=120,  # 120 second timeout for pip install
                )
                venv_created = True
            except subprocess.TimeoutExpired:
                pass  # venv creation timed out
            except Exception:
                pass  # venv creation is optional

        result = {
            "status": "created",
            "project_name": project_name,
            "project_path": str(project_dir),
            "files_created": [
                "agents.py",
                "main.py",
                "README.md",
                ".gitignore",
                ".qoder/mcp.json",
            ],
        }

        if venv_created:
            result["venv"] = "created"
            result["files_created"].append(".venv/")
        else:
            result["venv"] = "skipped"

        result["next_steps"] = [
            f"cd {project_name}",
        ]
        if venv_created:
            if sys.platform == "win32":
                result["next_steps"].append(".venv\\Scripts\\activate   # Windows")
            else:
                result["next_steps"].append("source .venv/bin/activate  # Linux/macOS")
        result["next_steps"].append("python main.py")

        return result

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Read Project",
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    def read_project(project_path: str, file_name: str = "") -> dict:
        """
        Read project structure or a specific file's content.
        读取项目结构或特定文件的内容。

        Args:
            project_path: Path to the AACF project directory
            file_name: Specific file to read (optional, reads all if empty)
        """
        root = Path(project_path).resolve()

        if not root.exists():
            return {"error": f"Project directory '{project_path}' does not exist."}

        if file_name:
            # Read specific file
            file_path = root / file_name
            if not file_path.exists():
                return {"error": f"File '{file_name}' not found in {project_path}."}

            try:
                content = file_path.read_text(encoding="utf-8")
                return {"file": file_name, "path": str(file_path), "content": content}
            except Exception as e:
                return {"error": f"Error reading file: {e}"}

        # List project structure
        exclude_dirs = {".venv", "venv", "__pycache__", ".git", "node_modules"}
        files = []

        for item in sorted(root.rglob("*")):
            if any(excluded in item.parts for excluded in exclude_dirs):
                continue
            if item.name.startswith(".") and item.name != ".gitignore":
                continue
            rel_path = item.relative_to(root)
            if item.is_dir():
                files.append({"path": str(rel_path) + "/", "type": "directory"})
            else:
                files.append({"path": str(rel_path), "type": "file", "size": item.stat().st_size})

        return {"project_path": str(root), "files": files}

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Validate Project",
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    def validate_project(project_path: str) -> dict:
        """
        Validate an AACF project's structure and configuration.
        验证 AACF 项目的结构和配置。

        Checks:
        - Required files exist (agents.py, main.py)
        - agents.py contains @app.node decorated functions
        - main.py imports from agents
        - LLMConfig is properly configured

        Args:
            project_path: Path to the AACF project directory
        """
        root = Path(project_path).resolve()
        issues = []
        warnings = []

        # Check required files
        agents_file = root / "agents.py"
        main_file = root / "main.py"

        if not agents_file.exists():
            issues.append("Missing required file: agents.py")
        if not main_file.exists():
            issues.append("Missing required file: main.py")

        if issues:
            return {"valid": False, "issues": issues, "warnings": warnings}

        # Validate agents.py
        agents_content = agents_file.read_text(encoding="utf-8")

        if "from aacf import AACF" not in agents_content:
            issues.append("agents.py does not import AACF")

        if "LLMConfig" not in agents_content:
            warnings.append("agents.py does not configure LLMConfig (will use defaults)")

        if "@app.node" not in agents_content:
            issues.append("agents.py contains no @app.node decorated functions")

        # Validate main.py
        main_content = main_file.read_text(encoding="utf-8")

        if "from agents import" not in main_content:
            warnings.append("main.py does not import from agents module")

        if '__name__ == "__main__"' not in main_content:
            warnings.append("main.py missing if __name__ == '__main__' guard")

        # Check for common issues
        if 'model=""' in agents_content or "model=''" in agents_content:
            warnings.append("LLMConfig model is empty string")

        if 'url=""' in agents_content or "url=''" in agents_content:
            warnings.append("LLMConfig url is empty string")

        # Build result
        result = {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
        }
        return result
