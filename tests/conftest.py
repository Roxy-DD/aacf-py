# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 AACF Contributors
"""
Pytest conftest — disable atexit docstring injection during tests.
测试期间禁用 atexit docstring 注入，防止测试文件被修改。
"""
import atexit
import pytest


@pytest.fixture(autouse=True)
def _disable_atexit_injection():
    """
    Clear the AACF node registry after each test so the atexit hook
    has nothing to inject, preventing test file corruption.
    """
    yield
    import aacf.core as core
    core._AACF_NODE_REGISTRY.clear()
