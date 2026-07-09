# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 AACF Contributors
"""
Tests for DAG caching and hash detection / DAG 缓存与哈希检测测试
"""
import pytest
from aacf.compiler import DependencyAnalyzer, DAGCache, AtomicScheduler, AtomicNodeConfig


# ─── DAG Hash Tests / DAG 哈希测试 ───


class TestDAGHash:
    """DAG 哈希计算测试"""

    def test_hash_stable(self):
        """测试相同结构生成相同哈希"""
        analyzer1 = DependencyAnalyzer()
        analyzer1.register_node("a", params=["x"])
        analyzer1.register_node("b", params=["a"])
        analyzer1.analyze()
        hash1 = analyzer1.compute_dag_hash()

        analyzer2 = DependencyAnalyzer()
        analyzer2.register_node("a", params=["x"])
        analyzer2.register_node("b", params=["a"])
        analyzer2.analyze()
        hash2 = analyzer2.compute_dag_hash()

        assert hash1 == hash2

    def test_hash_changes_with_structure(self):
        """测试结构变化导致哈希变化"""
        analyzer = DependencyAnalyzer()
        analyzer.register_node("a", params=["x"])
        analyzer.register_node("b", params=["a"])
        analyzer.analyze()
        hash1 = analyzer.compute_dag_hash()

        # Add a new node / 添加新节点
        analyzer.register_node("c", params=["b"])
        analyzer.analyze()
        hash2 = analyzer.compute_dag_hash()

        assert hash1 != hash2

    def test_hash_changes_with_dependencies(self):
        """测试依赖关系变化导致哈希变化"""
        analyzer1 = DependencyAnalyzer()
        analyzer1.register_node("a", params=["x"])
        analyzer1.register_node("b", params=["a"])
        analyzer1.analyze()
        hash1 = analyzer1.compute_dag_hash()

        analyzer2 = DependencyAnalyzer()
        analyzer2.register_node("a", params=["x"])
        analyzer2.register_node("b", params=["x"])  # Different dependency / 不同的依赖
        analyzer2.analyze()
        hash2 = analyzer2.compute_dag_hash()

        assert hash1 != hash2

    def test_hash_is_sha256(self):
        """测试哈希是 SHA256 格式"""
        analyzer = DependencyAnalyzer()
        analyzer.register_node("a", params=["x"])
        analyzer.analyze()
        hash_val = analyzer.compute_dag_hash()

        assert len(hash_val) == 64  # SHA256 hex digest length / SHA256 十六进制长度
        assert all(c in "0123456789abcdef" for c in hash_val)


# ─── DAGCache Tests / DAGCache 测试 ───


class TestDAGCache:
    """DAGCache 增量缓存测试"""

    def test_cache_miss(self):
        """测试缓存未命中"""
        cache = DAGCache()
        analyzer = DependencyAnalyzer()
        analyzer.register_node("a", params=["x"])
        analyzer.analyze()

        dag_hash = analyzer.compute_dag_hash()
        assert not cache.has_valid_cache(dag_hash)
        assert cache.get(dag_hash) is None

    def test_cache_hit(self):
        """测试缓存命中"""
        cache = DAGCache()
        analyzer = DependencyAnalyzer()
        analyzer.register_node("a", params=["x"])
        analyzer.analyze()

        dag_hash = analyzer.compute_dag_hash()
        results = {"a": "result_a"}
        cache.set(dag_hash, results)

        assert cache.has_valid_cache(dag_hash)
        assert cache.get(dag_hash) == results

    def test_cache_invalidation(self):
        """测试缓存失效"""
        cache = DAGCache()
        analyzer = DependencyAnalyzer()
        analyzer.register_node("a", params=["x"])
        analyzer.analyze()

        dag_hash = analyzer.compute_dag_hash()
        cache.set(dag_hash, {"a": "result"})

        assert cache.has_valid_cache(dag_hash)
        cache.invalidate(dag_hash)
        assert not cache.has_valid_cache(dag_hash)

    def test_cache_clear(self):
        """测试清除所有缓存"""
        cache = DAGCache()
        analyzer = DependencyAnalyzer()
        analyzer.register_node("a", params=["x"])
        analyzer.analyze()

        hash1 = analyzer.compute_dag_hash()
        cache.set(hash1, {"a": "result1"})

        analyzer.register_node("b", params=["a"])
        analyzer.analyze()
        hash2 = analyzer.compute_dag_hash()
        cache.set(hash2, {"a": "result1", "b": "result2"})

        assert cache.has_valid_cache(hash1)
        assert cache.has_valid_cache(hash2)

        cache.clear()
        assert not cache.has_valid_cache(hash1)
        assert not cache.has_valid_cache(hash2)

    def test_cache_lru_eviction(self):
        """测试 LRU 缓存淘汰"""
        cache = DAGCache(max_cache_size=2)

        cache.set("hash1", {"result": 1})
        cache.set("hash2", {"result": 2})
        cache.set("hash3", {"result": 3})  # Should evict hash1 / 应该淘汰 hash1

        assert not cache.has_valid_cache("hash1")
        assert cache.has_valid_cache("hash2")
        assert cache.has_valid_cache("hash3")

    def test_cache_lru_access_order(self):
        """测试 LRU 访问顺序更新"""
        cache = DAGCache(max_cache_size=2)

        cache.set("hash1", {"result": 1})
        cache.set("hash2", {"result": 2})

        # Access hash1 to update its position / 访问 hash1 更新其位置
        cache.get("hash1")

        # Add hash3, should evict hash2 (least recently used) / 添加 hash3，应该淘汰 hash2
        cache.set("hash3", {"result": 3})

        assert cache.has_valid_cache("hash1")
        assert not cache.has_valid_cache("hash2")
        assert cache.has_valid_cache("hash3")

    def test_detect_changes_no_cache(self):
        """测试无缓存时检测变更"""
        cache = DAGCache()
        analyzer = DependencyAnalyzer()
        analyzer.register_node("a", params=["x"])
        analyzer.analyze()

        changed = cache.detect_changes(analyzer, dag_id="test")
        assert changed is True  # No previous cache / 无先前缓存

    def test_detect_changes_same_structure(self):
        """测试相同结构无变更"""
        cache = DAGCache()
        analyzer = DependencyAnalyzer()
        analyzer.register_node("a", params=["x"])
        analyzer.register_node("b", params=["a"])
        analyzer.analyze()

        # First detection / 首次检测
        changed1 = cache.detect_changes(analyzer, dag_id="test")
        assert changed1 is True

        # Second detection with same structure / 第二次检测相同结构
        changed2 = cache.detect_changes(analyzer, dag_id="test")
        assert changed2 is False

    def test_detect_changes_structure_modified(self):
        """测试结构修改后检测变更"""
        cache = DAGCache()
        analyzer = DependencyAnalyzer()
        analyzer.register_node("a", params=["x"])
        analyzer.analyze()

        # First detection / 首次检测
        cache.detect_changes(analyzer, dag_id="test")

        # Modify structure / 修改结构
        analyzer.register_node("b", params=["a"])
        analyzer.analyze()

        # Second detection should detect change / 第二次检测应检测到变更
        changed = cache.detect_changes(analyzer, dag_id="test")
        assert changed is True

    def test_cache_stats(self):
        """测试缓存统计"""
        cache = DAGCache(max_cache_size=10)

        cache.set("hash1", {"result": 1})
        cache.set("hash2", {"result": 2})

        stats = cache.get_cache_stats()
        assert stats["cache_size"] == 2
        assert stats["max_cache_size"] == 10
        assert "hash1" in stats["cache_keys"]
        assert "hash2" in stats["cache_keys"]


# ─── Integration: Cache with Scheduler / 集成：缓存与调度器 ───


class TestCacheIntegration:
    """缓存与调度器集成测试"""

    def test_scheduler_with_cache_enabled(self):
        """测试启用缓存的调度器"""
        scheduler = AtomicScheduler()

        call_count = 0

        def counting_func():
            nonlocal call_count
            call_count += 1
            return f"result_{call_count}"

        scheduler.add_node(
            "cached_node",
            func=counting_func,
            config=AtomicNodeConfig(cache_enabled=True),
        )

        # First execution / 首次执行
        results1 = scheduler.run_all()
        assert results1["cached_node"] == "result_1"
        assert call_count == 1

        # Reset scheduler but keep cache / 重置调度器但保留缓存
        scheduler = AtomicScheduler()
        scheduler.add_node(
            "cached_node",
            func=counting_func,
            config=AtomicNodeConfig(cache_enabled=True),
        )

        # Second execution should use cache / 第二次执行应使用缓存
        results2 = scheduler.run_all()
        # Note: Each AtomicNode has its own cache, so this will re-execute / 注意：每个 AtomicNode 有自己的缓存，所以会重新执行
        assert results2["cached_node"] == "result_2"
        assert call_count == 2

    def test_cache_ttl_expiry(self):
        """测试缓存 TTL 过期"""
        import time

        scheduler = AtomicScheduler()
        call_count = 0

        def counting_func():
            nonlocal call_count
            call_count += 1
            return f"result_{call_count}"

        # Create node with short TTL / 创建短 TTL 的节点
        node = scheduler.add_node(
            "ttl_node",
            func=counting_func,
            config=AtomicNodeConfig(cache_enabled=True, cache_ttl=1),  # 1 second / 1 秒
        )

        # First execution / 首次执行
        result1 = node.execute()
        assert result1.unwrap() == "result_1"
        assert call_count == 1

        # Immediate second execution should use cache / 立即第二次执行应使用缓存
        result2 = node.execute()
        assert result2.unwrap() == "result_1"
        assert call_count == 1

        # Wait for TTL to expire / 等待 TTL 过期
        time.sleep(1.5)

        # Third execution should re-compute / 第三次执行应重新计算
        result3 = node.execute()
        assert result3.unwrap() == "result_2"
        assert call_count == 2
