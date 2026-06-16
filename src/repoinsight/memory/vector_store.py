"""Agentic RAG 向量记忆：ChromaDB 存储代码片段，支持语义检索。

Agent 在分析过程中可主动调用 search_similar_code() 检索相似代码，
实现"Agent 自主决定何时检索"的 Agentic RAG 模式。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from repoinsight.config import settings


class CodeVectorStore:
    """代码片段向量存储。

    将代码文件切分为可检索的片段，Agent 通过语义搜索找到相关代码。
    底层使用 ChromaDB 持久化存储。

    设计原则：小接口 + 深实现。对外只有 store() 和 search() 两个方法。
    """

    def __init__(self, persist_dir: Path | None = None) -> None:
        """初始化向量存储。

        Args:
            persist_dir: ChromaDB 持久化目录，默认使用 settings 中的配置。
        """
        self._persist_dir: Path = persist_dir or settings.chroma_dir
        self._collection: Any = None  # ChromaDB collection，延迟加载

    @property
    def collection(self) -> Any:
        """延迟加载 ChromaDB collection，避免启动时导入开销。"""
        if self._collection is None:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            self._persist_dir.mkdir(parents=True, exist_ok=True)
            client: Any = chromadb.PersistentClient(
                path=str(self._persist_dir),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._collection = client.get_or_create_collection(
                name="repoinsight_code_snippets",
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def store(self, repo_name: str, snippets: list[dict[str, str]]) -> int:
        """将代码片段存入向量数据库。

        Args:
            repo_name: 仓库名称，用作命名空间前缀。
            snippets: 代码片段列表，每项需包含:
                - file: 文件路径
                - content: 代码内容（会被向量化）
                - name: 函数/类名
                - line_start: 起始行号

        Returns:
            实际存入的片段数量。
        """
        if not snippets:
            return 0

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, str]] = []

        for i, s in enumerate(snippets):
            snippet_id: str = f"{repo_name}_{s['file']}_{s['name']}_{s.get('line_start', 0)}"
            ids.append(snippet_id)
            documents.append(s["content"])
            metadatas.append({
                "file": s["file"],
                "name": s["name"],
                "repo": repo_name,
                "line_start": str(s.get("line_start", 0)),
            })

        # ChromaDB 不接受空文档
        if not ids:
            return 0

        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )
        return len(ids)

    def search(
        self,
        query: str,
        repo_name: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """语义搜索相似代码片段。

        Args:
            query: 搜索查询（自然语言或代码片段）。
            repo_name: 限定搜索范围（None 表示跨仓库搜索）。
            top_k: 返回结果数量。

        Returns:
            匹配的代码片段列表，每项包含 file、name、content、distance。
        """
        where_filter: dict[str, Any] | None = None
        if repo_name:
            where_filter = {"repo": repo_name}

        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where_filter,
        )

        snippets: list[dict[str, Any]] = []
        if not results["ids"] or not results["ids"][0]:
            return snippets

        for i, doc_id in enumerate(results["ids"][0]):
            snippets.append({
                "id": doc_id,
                "file": results["metadatas"][0][i].get("file", ""),
                "name": results["metadatas"][0][i].get("name", ""),
                "content": results["documents"][0][i] if results["documents"] else "",
                "distance": results["distances"][0][i] if results.get("distances") else 0.0,
            })

        return snippets

    def store_files(self, repo_name: str, file_paths: list[Path]) -> int:
        """便捷方法：从文件列表批量存储代码片段。

        自动将文件按函数/类边界切分，避免整个文件存入。

        Args:
            repo_name: 仓库名称。
            file_paths: Python 文件路径列表。

        Returns:
            存入的片段总数。
        """
        import ast

        all_snippets: list[dict[str, str]] = []

        for fp in file_paths:
            if not fp.exists() or fp.suffix != ".py":
                continue
            try:
                source: str = fp.read_text(encoding="utf-8", errors="ignore")
                tree: ast.AST = ast.parse(source)
            except (SyntaxError, UnicodeDecodeError):
                continue

            rel_path: str = str(fp)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    body: str = ast.get_source_segment(source, node) or ""
                    all_snippets.append({
                        "file": rel_path,
                        "content": body,
                        "name": node.name,
                        "line_start": str(node.lineno),
                    })
                elif isinstance(node, ast.ClassDef):
                    body = ast.get_source_segment(source, node) or ""
                    all_snippets.append({
                        "file": rel_path,
                        "content": body,
                        "name": node.name,
                        "line_start": str(node.lineno),
                    })

        return self.store(repo_name, all_snippets)

    def clear_repo(self, repo_name: str) -> int:
        """删除某个仓库的所有片段。

        Args:
            repo_name: 要清除的仓库名称。

        Returns:
            删除的片段数量（-1 表示未知）。
        """
        try:
            results = self.collection.get(where={"repo": repo_name})
            ids: list[str] = results.get("ids", [])
            if ids:
                self.collection.delete(ids=ids)
            return len(ids)
        except Exception:
            return -1


# 模块级单例
vector_store: CodeVectorStore = CodeVectorStore()
