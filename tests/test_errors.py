# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 AACF Contributors
"""
Tests for error hierarchy and ExecutionResult / 错误层次结构与 ExecutionResult 测试
"""

import pytest

from aacf.compiler import (
    AACFError,
    CircularDependencyError,
    DependencyError,
    ExecutionResult,
    NodeConfigError,
    NodeExecutionError,
    PipelineError,
)

# ─── Error Hierarchy Tests / 错误层次结构测试 ───


class TestErrorHierarchy:
    """错误类型层次结构测试"""

    def test_aacf_error_is_base(self):
        """测试 AACFError 是基类"""
        assert issubclass(CircularDependencyError, AACFError)
        assert issubclass(DependencyError, AACFError)
        assert issubclass(NodeExecutionError, AACFError)
        assert issubclass(NodeConfigError, AACFError)
        assert issubclass(PipelineError, AACFError)

    def test_circular_dependency_error(self):
        """测试循环依赖错误"""
        cycle = ["a", "b", "c", "a"]
        err = CircularDependencyError(cycle)
        assert err.cycle == cycle
        assert "a -> b -> c -> a" in str(err)
        assert "Circular dependency" in str(err)
        assert "循环依赖" in str(err)

    def test_node_execution_error(self):
        """测试节点执行错误"""
        err = NodeExecutionError("my_node", 3, "timeout")
        assert err.node_name == "my_node"
        assert err.attempts == 3
        assert err.cause == "timeout"
        assert "my_node" in str(err)
        assert "3 attempts" in str(err)
        assert "timeout" in str(err)

    def test_all_errors_are_exceptions(self):
        """测试所有错误都是 Exception 子类"""
        for err_cls in [
            AACFError,
            CircularDependencyError,
            DependencyError,
            NodeExecutionError,
            NodeConfigError,
            PipelineError,
        ]:
            assert issubclass(err_cls, Exception)


# ─── ExecutionResult Tests / ExecutionResult 测试 ───


class TestExecutionResult:
    """ExecutionResult 测试"""

    def test_success_creation(self):
        """测试创建成功结果"""
        result = ExecutionResult.success(value=42, node_name="test", attempts=1)
        assert result.is_ok()
        assert not result.is_err()
        assert result.unwrap() == 42
        assert result.node_name == "test"
        assert result.attempts == 1
        assert result.from_cache is False

    def test_failure_creation(self):
        """测试创建失败结果"""
        result = ExecutionResult.failure(error="boom", node_name="test", attempts=3)
        assert result.is_err()
        assert not result.is_ok()
        assert result.error == "boom"
        assert result.node_name == "test"
        assert result.attempts == 3

    def test_success_with_cache(self):
        """测试带缓存标记的成功结果"""
        result = ExecutionResult.success(value="cached_val", from_cache=True)
        assert result.is_ok()
        assert result.from_cache is True
        assert result.unwrap() == "cached_val"

    def test_unwrap_on_failure_raises(self):
        """测试失败时 unwrap 抛出异常"""
        result = ExecutionResult.failure(error="fail", node_name="n1", attempts=2)
        with pytest.raises(NodeExecutionError):
            result.unwrap()

    def test_unwrap_or_raise_on_failure(self):
        """测试失败时 unwrap_or_raise 抛出异常"""
        result = ExecutionResult.failure(error="fail", node_name="n1", attempts=1)
        with pytest.raises(NodeExecutionError):
            result.unwrap_or_raise()

    def test_unwrap_or_default(self):
        """测试 unwrap_or 返回默认值"""
        result = ExecutionResult.failure(error="fail")
        assert result.unwrap_or("default") == "default"

        result_ok = ExecutionResult.success(value="real")
        assert result_ok.unwrap_or("default") == "real"

    def test_error_info(self):
        """测试结构化错误信息"""
        result = ExecutionResult.failure(error="timeout", node_name="n1", attempts=3)
        info = result.error_info()
        assert info["node_name"] == "n1"
        assert info["error"] == "timeout"
        assert info["attempts"] == 3
        assert info["ok"] is False

    def test_map_success(self):
        """测试 map 对成功结果应用函数"""
        result = ExecutionResult.success(value=10, node_name="n1")
        mapped = result.map(lambda x: x * 2)
        assert mapped.is_ok()
        assert mapped.unwrap() == 20

    def test_map_failure(self):
        """测试 map 对失败结果直接返回"""
        result = ExecutionResult.failure(error="fail", node_name="n1")
        mapped = result.map(lambda x: x * 2)
        assert mapped.is_err()
        assert mapped.error == "fail"

    def test_map_exception(self):
        """测试 map 中函数抛异常时返回失败"""
        result = ExecutionResult.success(value=10, node_name="n1")
        mapped = result.map(lambda x: 1 / 0)
        assert mapped.is_err()
        assert "division by zero" in mapped.error

    def test_to_dict(self):
        """测试序列化为字典"""
        result = ExecutionResult.success(value=42, node_name="n1", attempts=1, from_cache=True)
        d = result.to_dict()
        assert d["ok"] is True
        assert d["node_name"] == "n1"
        assert d["value"] == 42
        assert d["attempts"] == 1
        assert d["from_cache"] is True

    def test_to_dict_failure(self):
        """测试失败结果序列化为字典"""
        result = ExecutionResult.failure(error="boom", node_name="n1", attempts=2)
        d = result.to_dict()
        assert d["ok"] is False
        assert d["value"] is None
        assert d["error"] == "boom"

    def test_repr_success(self):
        """测试成功结果的 repr"""
        result = ExecutionResult.success(value=42)
        assert "Ok(42)" in repr(result)

    def test_repr_success_cached(self):
        """测试缓存成功结果的 repr"""
        result = ExecutionResult.success(value=42, from_cache=True)
        assert "Ok(42)" in repr(result)
        assert "cached" in repr(result)

    def test_repr_failure(self):
        """测试失败结果的 repr"""
        result = ExecutionResult.failure(error="boom")
        assert "Err" in repr(result)
        assert "boom" in repr(result)

    def test_value_property_on_success(self):
        """测试成功时 value 属性"""
        result = ExecutionResult.success(value="hello")
        assert result.value == "hello"

    def test_value_property_on_failure(self):
        """测试失败时 value 属性抛出异常"""
        result = ExecutionResult.failure(error="fail")
        with pytest.raises(NodeExecutionError):
            _ = result.value

    def test_error_property_on_success(self):
        """测试成功时 error 属性为 None"""
        result = ExecutionResult.success(value=42)
        assert result.error is None
