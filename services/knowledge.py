from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class KnowledgeChunk:
    source: str
    title: str
    content: str


class KnowledgeBase:
    """轻量本地检索器：知识量较小时无需引入向量数据库。"""

    def __init__(self, directory: Path):
        self.directory = directory
        self.chunks = self._load_chunks()

    def _load_chunks(self) -> list[KnowledgeChunk]:
        chunks: list[KnowledgeChunk] = []
        for path in sorted(self.directory.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            current_title = path.stem
            current_lines: list[str] = []
            for line in text.splitlines():
                if line.startswith("## "):
                    if current_lines:
                        chunks.append(
                            KnowledgeChunk(path.name, current_title, "\n".join(current_lines).strip())
                        )
                    current_title = line[3:].strip()
                    current_lines = []
                elif not line.startswith("# "):
                    current_lines.append(line)
            if current_lines:
                chunks.append(
                    KnowledgeChunk(path.name, current_title, "\n".join(current_lines).strip())
                )
        return [chunk for chunk in chunks if chunk.content]

    @staticmethod
    def _terms(text: str) -> set[str]:
        normalized = re.sub(r"[，。！？、：；,.!?\s]+", "", text.lower())
        terms = {normalized}
        keywords = (
            "列名配置", "销售端", "医保端", "处方端", "处方药", "冲销",
            "销售医保", "处方医保", "文件", "字段", "错误", "密钥", "流程",
            "完全匹配", "不完全匹配", "械字号", "消字号",
        )
        terms.update(keyword for keyword in keywords if keyword in normalized)
        return {term for term in terms if term}

    def search(self, query: str, limit: int = 4) -> list[KnowledgeChunk]:
        terms = self._terms(query)
        scored = []
        for chunk in self.chunks:
            haystack = f"{chunk.source}{chunk.title}{chunk.content}".lower()
            score = sum((4 if term in chunk.title.lower() else 1) for term in terms if term in haystack)
            # 中文疑问词本身信息量低，需要把“有什么”优先指向内容/字段说明章节。
            if any(word in query for word in ("什么", "哪些")) and any(
                marker in chunk.title for marker in ("包含什么", "字段", "需要的材料")
            ):
                score += 8
            if score:
                scored.append((score, chunk))
        scored.sort(key=lambda item: (-item[0], item[1].source, item[1].title))
        return [chunk for _, chunk in scored[:limit]]

    def context(self, query: str, limit: int = 4) -> str:
        chunks = self.search(query, limit)
        if not chunks:
            chunks = self.chunks[:2]
        return "\n\n".join(
            f"来源：{chunk.source} / {chunk.title}\n{chunk.content}" for chunk in chunks
        )

    def section(self, title: str) -> str | None:
        """流程节点按标题读取固定建议，确保执行后的指引稳定且可维护。"""
        for chunk in self.chunks:
            if chunk.title == title:
                return chunk.content
        return None


def load_welcome_message(directory: Path) -> str:
    """首次欢迎语直接读取角色知识，确保角色修改只维护一个来源。"""
    knowledge = KnowledgeBase(directory)
    for chunk in knowledge.chunks:
        if chunk.title == "首次完整自我介绍":
            return chunk.content
    return "Hi，我是您的药店数据筛查小助手——查宝（药店版）。请告诉我需要筛查什么。"
