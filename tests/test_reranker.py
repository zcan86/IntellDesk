# -*- coding: utf-8 -*-
"""reranker 回归测试

守护 LLM 精排的阈值过滤逻辑：修复前 threshold=0.5 在 1-5 分制下是空操作
（所有 1~5 分都 >= 0.5），低分文档永远不会被剔除。
"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.rag import reranker


def _fake_client(json_content: str):
    """构造返回固定 JSON 的假 OpenAI 客户端"""
    msg = SimpleNamespace(message=SimpleNamespace(content=json_content))
    choices = SimpleNamespace(choices=[msg])
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: choices)))


def _docs(n=5):
    return [
        {"content": f"文档{i}内容", "source": "returns.md", "score": 0.5 - i * 0.05}
        for i in range(1, n + 1)
    ]


def _run_rerank(docs, json_content, threshold=3):
    reranker._client = _fake_client(json_content)  # 替换单例，绕过 _get_client 的懒加载
    return reranker.rerank("退货多久到账", docs, top_k=3, threshold=threshold)


class TestRerankThreshold:
    """阈值过滤：1-5 分制下低于阈值的文档应被剔除"""

    def test_low_score_doc_is_filtered(self):
        """LLM 给文档2打 1 分（完全无关）→ 应从结果中剔除"""
        result = _run_rerank(_docs(), '[{"id":1,"score":5},{"id":2,"score":1},{"id":3,"score":4}]')
        contents = [d["content"] for d in result]
        assert "文档1内容" in contents
        assert "文档3内容" in contents
        assert "文档2内容" not in contents  # 1 分 < 阈值 3，被过滤

    def test_all_above_threshold_kept(self):
        """全部分数达标 → 全部保留"""
        result = _run_rerank(_docs(), '[{"id":1,"score":5},{"id":2,"score":4},{"id":3,"score":3}]')
        assert len(result) == 3

    def test_quick_path_skips_rerank(self):
        """文档数 <= top_k → 不调 LLM，直接返回"""
        result = reranker.rerank("q", _docs(2), top_k=3, threshold=3)
        assert len(result) == 2

    def test_fusion_score_combines_both(self):
        """融合分 = 原始分×0.4 + LLM分/5×0.6"""
        docs = [
            {"content": "a", "source": "s", "score": 0.5},
            {"content": "b", "source": "s", "score": 0.4},
            {"content": "c", "source": "s", "score": 0.3},
            {"content": "d", "source": "s", "score": 0.2},
        ]
        result = _run_rerank(
            docs, '[{"id":1,"score":5},{"id":2,"score":4},{"id":3,"score":3},{"id":4,"score":3}]'
        )
        a = next(d for d in result if d["content"] == "a")
        # 0.5*0.4 + (5/5)*0.6 = 0.2 + 0.6 = 0.8
        assert abs(a["score"] - 0.8) < 1e-6
