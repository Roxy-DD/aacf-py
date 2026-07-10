# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 AACF Contributors
"""
MCP Tools: Project Management / 项目管理工具。

Tools for initializing, reading, and validating AACF projects.
初始化、读取和验证 AACF 项目的工具。
"""

import os
import subprocess
import sys
from pathlib import Path


def register_project_tools(mcp):
    """Register all project management tools with the MCP server."""

    @mcp.tool()
    def init_project(project_name: str, path: str = "") -> str:
        """
        Initialize a new AACF project with standard structure.
        初始化具有标准结构的新 AACF 项目。

        Creates:
        - agents.py: Node definitions / 节点定义
        - main.py: Entry point / 入口文件
        - README.md: Project documentation / 项目文档
        - .venv/: Virtual environment with aacf installed / 虚拟环境

        Args:
            project_name: Name of the new project directory
            path: Parent directory path (default: current directory)
        """
        parent = Path(path).resolve() if path else Path.cwd()
        project_dir = parent / project_name

        if project_dir.exists():
            return f"Error: Directory '{project_name}' already exists at {parent}."

        # Create project directory
        project_dir.mkdir(parents=True)

        # Create agents.py
        agents_content = '''# SPDX-License-Identifier: GPL-3.0
"""AI agent node definitions / AI 智能体节点定义。"""

from aacf import AACF, LLMConfig


app = AACF(
    __name__,
    config=LLMConfig(
        model="qwen2.5-7b-instruct",
        url="http://127.0.0.1:8080/v1/chat/completions",
        language="zh",  # "zh" (中文) or "en" (English)
    ),
)


@app.node(who="助手", what="向用户打招呼")
def hello(name: str):
    pass
'''
        (project_dir / "agents.py").write_text(agents_content, encoding="utf-8")

        # Create main.py
        main_content = '''# SPDX-License-Identifier: GPL-3.0
"""Application entry point / 应用入口文件。"""

from agents import hello


if __name__ == "__main__":
    print(hello(name="World"))
'''
        (project_dir / "main.py").write_text(main_content, encoding="utf-8")

        # Create README.md
        readme_content = f'''# {project_name}

An AACF-powered AI agent project.

## Quick Start

```bash
# Activate virtual environment
source .venv/bin/activate  # Linux/macOS
.venv\\Scripts\\activate   # Windows

# Run the project
python main.py
```
'''
        (project_dir / "README.md").write_text(readme_content, encoding="utf-8")

        # Create .gitignore
        gitignore_content = '''__pycache__/
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
'''
        (project_dir / ".gitignore").write_text(gitignore_content, encoding="utf-8")

        # Create virtual environment and install aacf
        venv_created = False
        try:
            subprocess.run(
                [sys.executable, "-m", "venv", ".venv"],
                cwd=project_dir,
                check=True,
                capture_output=True,
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
            )
            venv_created = True
        except Exception as e:
            pass  # venv creation is optional

        result_lines = [
            f"Project '{project_name}' created successfully at {project_dir}!",
            "",
            "Created files:",
            "  - agents.py (node definitions)",
            "  - main.py (entry point)",
            "  - README.md (documentation)",
            "  - .gitignore",
        ]

        if venv_created:
            result_lines.append("  - .venv/ (virtual environment with aacf installed)")
        else:
            result_lines.append(
                "  - .venv/ creation failed (please create manually with: python -m venv .venv)"
            )

        result_lines.extend([
            "",
            "Next steps:",
            f"  cd {project_name}",
        ])

        if venv_created:
            if sys.platform == "win32":
                result_lines.append("  .venv\\Scripts\\activate   # Windows")
            else:
                result_lines.append("  source .venv/bin/activate  # Linux/macOS")
            result_lines.append("  python main.py")
        else:
            result_lines.append("  # Activate your virtual environment first")
            result_lines.append("  python main.py")

        return "\n".join(result_lines)

    @mcp.tool()
    def read_project(project_path: str, file_name: str = "") -> str:
        """
        Read project structure or a specific file's content.
        读取项目结构或特定文件的内容。

        Args:
            project_path: Path to the AACF project directory
            file_name: Specific file to read (optional, reads all if empty)
        """
        root = Path(project_path).resolve()

        if not root.exists():
            return f"Error: Project directory '{project_path}' does not exist."

        if file_name:
            # Read specific file
            file_path = root / file_name
            if not file_path.exists():
                return f"Error: File '{file_name}' not found in {project_path}."

            try:
                content = file_path.read_text(encoding="utf-8")
                return f"=== {file_name} ===\n\n{content}"
            except Exception as e:
                return f"Error reading file: {e}"

        # List project structure
        lines = [f"Project structure at {root}:", ""]

        # Get all files (excluding .venv and __pycache__)
        exclude_dirs = {'.venv', 'venv', '__pycache__', '.git', 'node_modules'}

        for item in sorted(root.rglob("*")):
            # Skip excluded directories
            if any(excluded in item.parts for excluded in exclude_dirs):
                continue

            # Skip hidden files except .gitignore
            if item.name.startswith('.') and item.name != '.gitignore':
                continue

            # Calculate relative path
            rel_path = item.relative_to(root)

            if item.is_dir():
                lines.append(f"  {rel_path}/")
            else:
                size = item.stat().st_size
                lines.append(f"  {rel_path} ({size} bytes)")

        return "\n".join(lines)

    @mcp.tool()
    def validate_project(project_path: str) -> str:
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
            return "Validation failed:\n  - " + "\n  - ".join(issues)

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
        if not issues and not warnings:
            return "Project validation passed! All checks OK."

        result_lines = ["Project validation results:", ""]

        if issues:
            result_lines.append(f"Issues ({len(issues)}):")
            for issue in issues:
                result_lines.append(f"  [ERROR] {issue}")
            result_lines.append("")

        if warnings:
            result_lines.append(f"Warnings ({len(warnings)}):")
            for warning in warnings:
                result_lines.append(f"  [WARN] {warning}")
            result_lines.append("")

        if issues:
            result_lines.append("Validation: FAILED")
        else:
            result_lines.append("Validation: PASSED (with warnings)")

        return "\n".join(result_lines)
