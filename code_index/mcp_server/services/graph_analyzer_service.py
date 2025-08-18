from __future__ import annotations

from code_index.analyzer import SimpleAnalyzer
from code_index.analyzer.models import (
    CallGraph,
    Direction,
    FindPathsResult,
    GraphConstructOptions,
    PathReturnMode,
)
from code_index.models import PureDefinition

from .code_index_service import CodeIndexService


class GraphAnalyzerService:
    """A service for analyzing the call graph of a repository."""

    _instance: GraphAnalyzerService | None = None

    @classmethod
    def get_instance(cls) -> GraphAnalyzerService:
        """Get the singleton instance of GraphAnalyzerService."""
        if cls._instance is None:
            cls._instance = GraphAnalyzerService()
        return cls._instance

    def __init__(self):
        self._analyzer = SimpleAnalyzer()
        self._graph_cache: CallGraph | None = None

    def _get_graph(self) -> CallGraph:
        """Get the call graph, using a cache if available."""
        if self._graph_cache is not None:
            return self._graph_cache

        index = CodeIndexService.get_instance().index
        options = GraphConstructOptions(direction=Direction.FORWARD, compute_scc=True)
        graph = self._analyzer.get_call_graph(index, options)
        self._graph_cache = graph
        return graph

    def clear_cache(self) -> None:
        """Clear the graph cache. Call this when the index is rebuilt."""
        self._graph_cache = None

    def get_call_graph_overview(self):
        """
        Generate a general view/stat of the call graph.
        """
        from code_index.mcp_server.models import GraphOverviewResponse, SCCDetail, SCCOverview

        graph = self._get_graph()

        scc_details = [
            SCCDetail(
                scc_id=i,
                size=len(scc),
                nodes=[graph.nodes[node_idx] for node_idx in scc[:5]],  # show first 5 nodes
            )
            for i, scc in enumerate(graph.sccs)
        ]

        # Build adjacency list for determining starting nodes
        adj: dict[int, list[int]] = {}
        for edge in graph.edges:
            if edge.src not in adj:
                adj[edge.src] = []
            adj[edge.src].append(edge.dst)

        entrypoints = self._analyzer._determine_starting_nodes(graph, Direction.FORWARD, adj)
        endpoints = self._analyzer._determine_starting_nodes(graph, Direction.BACKWARD, adj)

        return GraphOverviewResponse(
            stats=graph.stats,
            scc_overview=SCCOverview(count=len(graph.sccs), details=scc_details),
            entrypoints=[graph.nodes[i] for i in entrypoints[:10]],
            endpoints=[graph.nodes[i] for i in endpoints[:10]],
        )

    def get_subgraph(self, roots: list[PureDefinition], depth: int) -> CallGraph:
        """
        Generate a subgraph of the call-graph from specific definition(s).
        """
        graph = self._get_graph()

        root_indices = [i for i, node in enumerate(graph.nodes) if node in roots]

        return self._analyzer.get_subgraph(graph, roots=root_indices, depth=depth)

    def find_paths(
        self,
        src: PureDefinition,
        dst: PureDefinition,
        k: int = 3,
        mode: PathReturnMode = PathReturnMode.HYBRID,
    ) -> FindPathsResult:
        """
        Find paths between two definitions.
        """
        graph = self._get_graph()

        try:
            src_idx = graph.nodes.index(src)
            dst_idx = graph.nodes.index(dst)
        except ValueError as e:
            raise ValueError(f"Source or destination node not found in graph: {e}") from e

        return self._analyzer.find_paths(graph, src_idx, dst_idx, k=k, return_mode=mode)

    def get_topological_order(
        self, direction: Direction = Direction.BACKWARD
    ) -> list[PureDefinition]:
        """
        Iterate the definitions topologically.
        BACKWARD (default) goes from deepest dependencies up to entrypoints.
        """
        graph = self._get_graph()
        return list(self._analyzer.bfs_traverse_graph(graph, direction=direction))
