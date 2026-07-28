# -*- coding: utf-8 -*-
"""RAG 模块测试：文档加载、TF-IDF 索引构建、检索"""

import sys
from pathlib import Path

# 确保项目根目录在 import 路径中
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.rag.loader import build_index, search_knowledge, get_index_status


class TestRAGIndex:
    """TF-IDF 索引构建测试"""

    def test_build_index(self):
        """索引构建成功，返回 True 且状态就绪"""
        ok = build_index(force_rebuild=True)
        assert ok is True
        status = get_index_status()
        assert status["ready"] is True
        assert status["chunk_count"] > 0

    def test_build_index_skips_when_ready(self):
        """已就绪时不重复构建"""
        build_index(force_rebuild=True)
        ok = build_index()  # 不传 force_rebuild
        assert ok is True

    def test_build_index_nonexistent_dir(self):
        """不存在的目录返回 False"""
        ok = build_index(docs_dir="/nonexistent/path", force_rebuild=True)
        assert ok is False


class TestRAGSearch:
    """TF-IDF 检索测试"""

    def setup_method(self):
        build_index(force_rebuild=True)

    def test_search_returns_results(self):
        """正常检索返回结果"""
        results = search_knowledge("免费版能用 API 吗？")
        assert len(results) > 0
        for r in results:
            assert "content" in r
            assert "source" in r
            assert "score" in r

    def test_search_irrelevant_query(self):
        """不相关查询返回空或低分"""
        results = search_knowledge("火星上有没有水")
        # 要么无结果，要么分数很低
        if results:
            assert results[0]["score"] < 0.5  # 语义不相关，相似度应低

    def test_search_top_k(self):
        """top_k 参数生效"""
        results_2 = search_knowledge("API", top_k=2)
        results_5 = search_knowledge("API", top_k=5)
        assert len(results_2) <= 2
        assert len(results_5) <= 5

    def test_search_empty_query(self):
        """空查询不崩溃"""
        results = search_knowledge("")
        assert isinstance(results, list)
