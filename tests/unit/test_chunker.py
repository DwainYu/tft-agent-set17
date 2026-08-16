"""Unit tests for the document chunking stage (api.services.rag.chunker)."""
from __future__ import annotations

import pytest

from api.services.rag.chunker import (
    Chunk,
    MarkdownSplitter,
    RecursiveCharacterSplitter,
)


# ---------------------------------------------------------------------------
# RecursiveCharacterSplitter
# ---------------------------------------------------------------------------

class TestRecursiveCharacterSplitter:
    def test_short_text_returns_single_chunk(self):
        splitter = RecursiveCharacterSplitter(chunk_size=100, chunk_overlap=10)
        assert splitter.split("这是一段很短的文本。") == ["这是一段很短的文本。"]

    def test_empty_and_whitespace_input(self):
        splitter = RecursiveCharacterSplitter()
        assert splitter.split("") == []
        assert splitter.split("   \n\n  ") == []

    def test_long_text_chunks_respect_size_limit(self):
        # Build a long paragraph of CJK sentences.
        sentence = "云顶之弈是一套自走棋玩法。"
        text = sentence * 40
        splitter = RecursiveCharacterSplitter(chunk_size=120, chunk_overlap=20)
        chunks = splitter.split(text)
        assert len(chunks) > 1
        # Every chunk must stay within the size budget (with a small tolerance
        # for a single indivisible piece).
        for c in chunks:
            assert len(c) <= 120 + len(sentence)

    def test_no_content_lost(self):
        sentence = "这句话用来测试内容不丢失。"
        text = sentence * 30
        splitter = RecursiveCharacterSplitter(chunk_size=100, chunk_overlap=15)
        chunks = splitter.split(text)
        # Every original sentence should appear at least once. Overlap may
        # duplicate some sentences across chunk boundaries (that is intended),
        # so we assert a lower bound rather than an exact count.
        joined = "".join(chunks)
        assert sentence in joined
        assert joined.count("测试内容不丢失") >= 30

    def test_overlap_between_adjacent_chunks(self):
        words = [f"word{i}" for i in range(60)]
        text = " ".join(words)
        splitter = RecursiveCharacterSplitter(chunk_size=80, chunk_overlap=30)
        chunks = splitter.split(text)
        assert len(chunks) >= 2
        # The tail of chunk i should overlap the head of chunk i+1.
        overlap_found = False
        for a, b in zip(chunks, chunks[1:]):
            tail_words = set(a.split(" ")[-3:])
            head_words = set(b.split(" ")[:3])
            if tail_words & head_words:
                overlap_found = True
        assert overlap_found

    def test_invalid_overlap_raises(self):
        with pytest.raises(ValueError):
            RecursiveCharacterSplitter(chunk_size=50, chunk_overlap=50)


# ---------------------------------------------------------------------------
# MarkdownSplitter
# ---------------------------------------------------------------------------

SAMPLE_MD = """# 锐雯主C攻略

前言：本攻略基于 16.13 版本数据。

## 阵容概览

这是一套以锐雯为核心的物理输出阵容，适合前期连胜开局。

## 装备推荐

### 主C装备

锐雯推荐装备为泰坦的坚决、饮血剑与巨人杀手。

### 坦克装备

前排坦克优先反甲与龙牙。

## 运营思路

前期用低费卡过渡，七级开始搜锐雯三星。
"""


class TestMarkdownSplitter:
    def test_extracts_title(self):
        assert MarkdownSplitter.extract_title(SAMPLE_MD) == "锐雯主C攻略"

    def test_heading_paths_are_scoped(self):
        splitter = MarkdownSplitter(chunk_size=500, chunk_overlap=20)
        chunks = splitter.split(SAMPLE_MD, source="riven.md")
        paths = {c.metadata["heading_path"] for c in chunks}
        # The nested '主C装备' chunk must carry its full ancestor path.
        assert "装备推荐 > 主C装备" in paths
        assert "阵容概览" in paths

    def test_metadata_carries_source_and_title(self):
        splitter = MarkdownSplitter(chunk_size=500, chunk_overlap=20)
        chunks = splitter.split(SAMPLE_MD, source="riven.md")
        assert chunks, "expected at least one chunk"
        for c in chunks:
            assert c.metadata["source"] == "riven.md"
            assert c.metadata["title"] == "锐雯主C攻略"
            assert isinstance(c.metadata["chunk_index"], int)

    def test_heading_prefixed_content_is_self_contained(self):
        splitter = MarkdownSplitter(chunk_size=500, chunk_overlap=20)
        chunks = splitter.split(SAMPLE_MD, source="riven.md")
        # The chunk about 主C装备 should mention its section in the content.
        main_c = [c for c in chunks if "泰坦的坚决" in c.content]
        assert main_c
        assert "主C装备" in main_c[0].content

    def test_chunk_index_is_sequential(self):
        splitter = MarkdownSplitter(chunk_size=50, chunk_overlap=10)
        chunks = splitter.split(SAMPLE_MD, source="riven.md")
        assert [c.metadata["chunk_index"] for c in chunks] == list(range(len(chunks)))

    def test_prewrite_content_uses_empty_heading_path(self):
        md = "没有标题的开场白内容。\n\n## 第一节\n\n正文内容。"
        splitter = MarkdownSplitter(chunk_size=500, chunk_overlap=10)
        chunks = splitter.split(md, source="x.md")
        preface = [c for c in chunks if "开场白" in c.content]
        assert preface
        assert preface[0].metadata["heading_path"] == ""

    def test_split_file_and_directory(self, tmp_path):
        (tmp_path / "a.md").write_text("# A\n\n内容甲。", encoding="utf-8")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.md").write_text("# B\n\n内容乙。", encoding="utf-8")

        splitter = MarkdownSplitter(chunk_size=200, chunk_overlap=10)
        file_chunks = splitter.split_file(tmp_path / "a.md")
        assert file_chunks[0].metadata["source"] == "a.md"

        dir_chunks = splitter.split_directory(tmp_path)
        sources = {c.metadata["source"] for c in dir_chunks}
        assert sources == {"a.md", "b.md"}
