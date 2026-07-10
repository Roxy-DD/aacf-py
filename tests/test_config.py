# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 AACF Contributors
"""
Tests for LLMConfig / LLMConfig 测试
"""

from aacf import LLMConfig


class TestLLMConfig:
    """LLMConfig 测试类"""

    def test_default_config(self):
        """测试默认配置"""
        config = LLMConfig()
        assert config.get_dict() == {}
        assert config.get_language() == "zh"

    def test_custom_config(self):
        """测试自定义配置"""
        config = LLMConfig(
            model="gpt-4",
            url="https://api.openai.com/v1/chat/completions",
            temperature=0.5,
            max_tokens=2048,
            language="en",
        )
        d = config.get_dict()
        assert d["model"] == "gpt-4"
        assert d["url"] == "https://api.openai.com/v1/chat/completions"
        assert d["temperature"] == 0.5
        assert d["max_tokens"] == 2048
        assert d["language"] == "en"

    def test_derive_config(self):
        """测试配置派生"""
        base = LLMConfig(model="qwen2.5-7b", temperature=0.7)
        derived = base(temperature=1.2, stream=True)

        # 原配置不变
        assert base.get_dict()["temperature"] == 0.7
        assert "stream" not in base.get_dict()

        # 派生配置已更新
        assert derived.get_dict()["temperature"] == 1.2
        assert derived.get_dict()["stream"] is True
        assert derived.get_dict()["model"] == "qwen2.5-7b"

    def test_language_default(self):
        """测试默认语言"""
        config = LLMConfig()
        assert config.get_language() == "zh"

    def test_language_custom(self):
        """测试自定义语言"""
        config = LLMConfig(language="en")
        assert config.get_language() == "en"

    def test_derive_preserves_original(self):
        """测试派生不影响原配置"""
        original = LLMConfig(model="test", temperature=0.5)
        derived = original(model="new-model")

        assert original.get_dict()["model"] == "test"
        assert derived.get_dict()["model"] == "new-model"
        assert original.get_dict()["temperature"] == 0.5
        assert derived.get_dict()["temperature"] == 0.5
