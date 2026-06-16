"""Graph-RAG 知识图谱：基于依赖图沿调用链检索代码上下文。

实现 JD 要求的 Graph-RAG 记忆增强：不单独检索单个文件，
而是沿依赖图边检索调用者和被调用者，提供更完整的代码上下文。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx


class DependencyGraphStore:
    """依赖图知识图谱存储。

    将仓库的模块依赖关系加载为有向图，支持沿调用链的上下文检索。
    Graph-RAG 的核心思想：当 Agent 分析某个模块时，自动拉取
    其上下游的代码，而非孤立的片段。

    设计原则：小接口 + 深实现。
    """

    def __init__(self) -> None:
        """初始化空依赖图。"""
        self._graph: nx.DiGraph = nx.DiGraph()
        self._loaded: bool = False

    # ===== 数据加载 =====

    def load_from_json(self, repo_graph_json: str | dict[str, Any]) -> int:
        """从 Repo Crawler 输出的 repo_graph 加载依赖图。

        Args:
            repo_graph_json: repo_graph 的 JSON 字符串或已解析的 dict。

        Returns:
            图中节点数量，0 表示加载失败。
        """
        if isinstance(repo_graph_json, str):
            try:
                data: dict[str, Any] = json.loads(repo_graph_json)
            except json.JSONDecodeError:
                return 0
        else:
            data = repo_graph_json

        graph_data: dict[str, Any] = data.get("dependency_graph", {})
        if not graph_data:
            return 0

        # 清空旧数据
        self._graph.clear()

        # 加载节点及其属性
        for node in graph_data.get("nodes", []):
            self._graph.add_node(
                node["id"],
                file=node.get("file", ""),
                loc=node.get("loc", 0),
            )

        # 加载边
        for edge in graph_data.get("edges", []):
            self._graph.add_edge(edge["source"], edge["target"])

        self._loaded = True
        return self._graph.number_of_nodes()

    @property
    def is_loaded(self) -> bool:
        """依赖图是否已加载。"""
        return self._loaded

    # ===== 基础查询 =====

    def get_direct_dependents(self, module: str) -> list[str]:
        """查询直接依赖此模块的其他模块（谁引用了我）。

        Args:
            module: 模块名（如 "repoinsight.tools.repo_tools"）。

        Returns:
            直接调用者的模块名列表。
        """
        if module not in self._graph:
            return []
        return list(self._graph.predecessors(module))

    def get_direct_dependencies(self, module: str) -> list[str]:
        """查询此模块直接依赖的其他模块（我引用了谁）。

        Args:
            module: 模块名。

        Returns:
            直接依赖的模块名列表。
        """
        if module not in self._graph:
            return []
        return list(self._graph.successors(module))

    # ===== 图遍历查询（Graph-RAG 核心） =====

    def get_impact_zone(self, module: str, max_depth: int = 3) -> list[dict[str, Any]]:
        """查询"改动影响范围"：修改此模块会波及哪些模块。

        从 module 开始沿后继（被依赖方向）做 BFS，返回受影响模块列表。
        这是 Graph-RAG 的核心方法：Agent 审查某个文件时，自动拉取
        所有可能被影响的文件。

        Args:
            module: 起始模块。
            max_depth: BFS 最大深度（防止大图爆炸）。

        Returns:
            受影响模块列表，每项含 name、distance、file。
        """
        if module not in self._graph:
            return []

        result: list[dict[str, Any]] = []
        visited: set[str] = {module}
        queue: list[tuple[str, int]] = [(m, 1) for m in self._graph.successors(module)]

        while queue:
            current, depth = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            result.append({
                "name": current,
                "distance": depth,
                "file": self._graph.nodes[current].get("file", ""),
            })

            if depth < max_depth:
                for neighbor in self._graph.successors(current):
                    if neighbor not in visited:
                        queue.append((neighbor, depth + 1))

        return result

    def get_dependency_chain(self, module: str, max_depth: int = 3) -> list[dict[str, Any]]:
        """查询"依赖链条"：此模块沿依赖方向（前驱）的上下文。

        返回模块依赖的库/模块链，帮助 Agent 理解"这段代码为什么会这样写"。

        Args:
            module: 起始模块。
            max_depth: BFS 最大深度。

        Returns:
            依赖链列表。
        """
        if module not in self._graph:
            return []

        result: list[dict[str, Any]] = []
        visited: set[str] = {module}
        queue: list[tuple[str, int]] = [(m, 1) for m in self._graph.predecessors(module)]

        while queue:
            current, depth = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            result.append({
                "name": current,
                "distance": depth,
                "file": self._graph.nodes[current].get("file", ""),
            })

            if depth < max_depth:
                for neighbor in self._graph.predecessors(current):
                    if neighbor not in visited:
                        queue.append((neighbor, depth + 1))

        return result

    def find_path(self, source: str, target: str) -> list[str] | None:
        """查找两个模块之间的依赖路径。

        Args:
            source: 源模块。
            target: 目标模块。

        Returns:
            路径上的模块列表（含首尾），无路径返回 None。
        """
        if source not in self._graph or target not in self._graph:
            return None
        try:
            path: list[str] = nx.shortest_path(self._graph, source=source, target=target)
            return path
        except nx.NetworkXNoPath:
            return None

    def get_circular_dependencies(self) -> list[list[str]]:
        """检测图中的循环依赖。

        Returns:
            每个环的节点列表。空列表表示无循环依赖。
        """
        cycles: list[list[str]] = []
        try:
            raw_cycles: list[list[str]] = list(nx.simple_cycles(self._graph))
            for cycle in raw_cycles:
                if len(cycle) > 1:  # 忽略自环
                    cycles.append(cycle)
        except Exception:
            pass
        return cycles

    def get_centrality(self, top_n: int = 10) -> list[dict[str, float]]:
        """计算模块的 PageRank 中心度，识别项目中最关键的模块。

        Args:
            top_n: 返回前 N 个。

        Returns:
            按中心度降序排列的模块列表。
        """
        if self._graph.number_of_nodes() == 0:
            return []

        pr: dict[str, float] = nx.pagerank(self._graph)
        sorted_pr: list[tuple[str, float]] = sorted(
            pr.items(), key=lambda x: x[1], reverse=True
        )
        return [
            {"name": name, "score": round(score, 4)}
            for name, score in sorted_pr[:top_n]
        ]

    # ===== 统计信息 =====

    def summary(self) -> dict[str, int]:
        """返回图的基本统计信息。"""
        return {
            "nodes": self._graph.number_of_nodes(),
            "edges": self._graph.number_of_edges(),
            "density": round(nx.density(self._graph), 4),
            "connected_components": nx.number_weakly_connected_components(self._graph),
        }


# 模块级单例
graph_store: DependencyGraphStore = DependencyGraphStore()
