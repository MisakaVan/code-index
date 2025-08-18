"""Tests for BFS traversal of call graphs.

This module tests the bfs_traverse_graph method in SimpleAnalyzer,
covering scenarios with and without SCCs, and forward/backward traversal.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from code_index.analyzer.models import (
    CallEdge,
    CallGraph,
    Direction,
    EdgeKind,
)
from code_index.analyzer.simple_analyzer import SimpleAnalyzer
from code_index.models import (
    CodeLocation,
    Function,
    PureDefinition,
)


def _loc(file: str, base: int) -> CodeLocation:
    """Helper to create a CodeLocation."""
    return CodeLocation(
        file_path=Path(file),
        start_lineno=base,
        start_col=0,
        end_lineno=base,
        end_col=10,
        start_byte=base * 10,
        end_byte=base * 10 + 5,
    )


def _create_simple_linear_graph() -> tuple[CallGraph, dict[str, int]]:
    """Create a simple linear call graph: A -> B -> C -> D."""
    analyzer = SimpleAnalyzer()

    # Create nodes
    A = PureDefinition(location=_loc("test.py", 10))
    B = PureDefinition(location=_loc("test.py", 20))
    C = PureDefinition(location=_loc("test.py", 30))
    D = PureDefinition(location=_loc("test.py", 40))

    nodes = [A, B, C, D]
    owners = [Function(name="A"), Function(name="B"), Function(name="C"), Function(name="D")]

    # Create edges: A->B, B->C, C->D
    edges = [
        CallEdge(src=0, dst=1, kind=EdgeKind.MUST),  # A -> B
        CallEdge(src=1, dst=2, kind=EdgeKind.MUST),  # B -> C
        CallEdge(src=2, dst=3, kind=EdgeKind.MUST),  # C -> D
    ]

    graph = CallGraph(
        nodes=nodes,
        owners=owners,
        edges=edges,
        sccs=[],  # No SCCs computed
        scc_edges=[],
        unresolved=[],
    )

    # Return mapping of names to indices for easy testing
    name_to_idx = {"A": 0, "B": 1, "C": 2, "D": 3}
    return graph, name_to_idx


def _create_graph_with_sccs() -> tuple[CallGraph, dict[str, int]]:
    """Create a call graph with SCCs: A -> B <-> C -> D."""
    analyzer = SimpleAnalyzer()

    # Create nodes
    A = PureDefinition(location=_loc("test.py", 10))
    B = PureDefinition(location=_loc("test.py", 20))
    C = PureDefinition(location=_loc("test.py", 30))
    D = PureDefinition(location=_loc("test.py", 40))

    nodes = [A, B, C, D]
    owners = [Function(name="A"), Function(name="B"), Function(name="C"), Function(name="D")]

    # Create edges: A->B, B->C, C->B, C->D (B and C form a cycle)
    edges = [
        CallEdge(src=0, dst=1, kind=EdgeKind.MUST),  # A -> B
        CallEdge(src=1, dst=2, kind=EdgeKind.MUST),  # B -> C
        CallEdge(src=2, dst=1, kind=EdgeKind.MUST),  # C -> B (cycle)
        CallEdge(src=2, dst=3, kind=EdgeKind.MUST),  # C -> D
    ]

    # Define SCCs: {A}, {B,C}, {D}
    sccs = [
        [0],  # SCC 0: A
        [1, 2],  # SCC 1: B, C
        [3],  # SCC 2: D
    ]

    # SCC edges: SCC0 -> SCC1, SCC1 -> SCC2
    scc_edges = [(0, 1), (1, 2)]

    graph = CallGraph(
        nodes=nodes,
        owners=owners,
        edges=edges,
        sccs=sccs,
        scc_edges=scc_edges,
        unresolved=[],
    )

    name_to_idx = {"A": 0, "B": 1, "C": 2, "D": 3}
    return graph, name_to_idx


def _create_disconnected_graph() -> tuple[CallGraph, dict[str, int]]:
    """Create a disconnected graph: A -> B, C -> D (two separate components)."""
    A = PureDefinition(location=_loc("test.py", 10))
    B = PureDefinition(location=_loc("test.py", 20))
    C = PureDefinition(location=_loc("test.py", 30))
    D = PureDefinition(location=_loc("test.py", 40))

    nodes = [A, B, C, D]
    owners = [Function(name="A"), Function(name="B"), Function(name="C"), Function(name="D")]

    # Create edges: A->B, C->D (disconnected)
    edges = [
        CallEdge(src=0, dst=1, kind=EdgeKind.MUST),  # A -> B
        CallEdge(src=2, dst=3, kind=EdgeKind.MUST),  # C -> D
    ]

    graph = CallGraph(
        nodes=nodes,
        owners=owners,
        edges=edges,
        sccs=[],  # No SCCs computed
        scc_edges=[],
        unresolved=[],
    )

    name_to_idx = {"A": 0, "B": 1, "C": 2, "D": 3}
    return graph, name_to_idx


class TestBFSTraverseGraph:
    """Test class for BFS traversal functionality."""

    def test_empty_graph(self):
        """Test BFS traversal on an empty graph."""
        analyzer = SimpleAnalyzer()
        empty_graph = CallGraph(nodes=[], owners=[], edges=[])

        result = list(analyzer.bfs_traverse_graph(empty_graph))
        assert result == []

    def test_single_node_graph(self):
        """Test BFS traversal on a graph with a single node."""
        analyzer = SimpleAnalyzer()

        A = PureDefinition(location=_loc("test.py", 10))
        graph = CallGraph(
            nodes=[A],
            owners=[Function(name="A")],
            edges=[],
        )

        result = list(analyzer.bfs_traverse_graph(graph))
        assert len(result) == 1
        assert result[0] == A

    def test_linear_graph_forward_no_scc(self):
        """Test forward BFS traversal on linear graph without SCCs."""
        analyzer = SimpleAnalyzer()
        graph, name_to_idx = _create_simple_linear_graph()

        result = list(analyzer.bfs_traverse_graph(graph, direction=Direction.FORWARD))

        # Should start from A (no incoming edges) and traverse in BFS order
        assert len(result) == 4
        result_indices = [graph.nodes.index(node) for node in result]

        # A should come first (it has no incoming edges)
        assert result_indices[0] == name_to_idx["A"]
        # The rest should follow the dependency chain
        assert name_to_idx["B"] in result_indices
        assert name_to_idx["C"] in result_indices
        assert name_to_idx["D"] in result_indices

    def test_linear_graph_backward_no_scc(self):
        """Test backward BFS traversal on linear graph without SCCs."""
        analyzer = SimpleAnalyzer()
        graph, name_to_idx = _create_simple_linear_graph()

        result = list(analyzer.bfs_traverse_graph(graph, direction=Direction.BACKWARD))

        # Should start from D (no outgoing edges) and traverse backward
        assert len(result) == 4
        result_indices = [graph.nodes.index(node) for node in result]

        # D should come first (it has no outgoing edges)
        assert result_indices[0] == name_to_idx["D"]
        # All nodes should be included
        assert name_to_idx["A"] in result_indices
        assert name_to_idx["B"] in result_indices
        assert name_to_idx["C"] in result_indices

    def test_graph_with_sccs_forward(self):
        """Test forward BFS traversal on graph with SCCs."""
        analyzer = SimpleAnalyzer()
        graph, name_to_idx = _create_graph_with_sccs()

        result = list(analyzer.bfs_traverse_graph(graph, direction=Direction.FORWARD))

        assert len(result) == 4
        result_indices = [graph.nodes.index(node) for node in result]

        # Should start from SCC with no incoming edges (SCC 0: A)
        assert result_indices[0] == name_to_idx["A"]

        # B and C should come next (they're in SCC 1)
        bc_positions = [
            result_indices.index(name_to_idx["B"]),
            result_indices.index(name_to_idx["C"]),
        ]
        assert all(pos > 0 for pos in bc_positions)  # Both after A

        # D should come last (SCC 2)
        d_position = result_indices.index(name_to_idx["D"])
        assert d_position > max(bc_positions)

    def test_graph_with_sccs_backward(self):
        """Test backward BFS traversal on graph with SCCs."""
        analyzer = SimpleAnalyzer()
        graph, name_to_idx = _create_graph_with_sccs()

        result = list(analyzer.bfs_traverse_graph(graph, direction=Direction.BACKWARD))

        assert len(result) == 4
        result_indices = [graph.nodes.index(node) for node in result]

        # Should start from SCC with no outgoing edges (SCC 2: D)
        assert result_indices[0] == name_to_idx["D"]

        # All nodes should be included
        assert name_to_idx["A"] in result_indices
        assert name_to_idx["B"] in result_indices
        assert name_to_idx["C"] in result_indices

    def test_disconnected_graph_forward(self):
        """Test BFS traversal on disconnected graph."""
        analyzer = SimpleAnalyzer()
        graph, name_to_idx = _create_disconnected_graph()

        result = list(analyzer.bfs_traverse_graph(graph, direction=Direction.FORWARD))

        # Should include all nodes despite disconnection
        assert len(result) == 4
        result_indices = [graph.nodes.index(node) for node in result]

        # Both A and C should be starting points (no incoming edges)
        first_two = result_indices[:2]
        assert {name_to_idx["A"], name_to_idx["C"]}.issubset(set(first_two))

        # All nodes should be included
        assert set(result_indices) == {0, 1, 2, 3}

    def test_disconnected_graph_backward(self):
        """Test backward BFS traversal on disconnected graph."""
        analyzer = SimpleAnalyzer()
        graph, name_to_idx = _create_disconnected_graph()

        result = list(analyzer.bfs_traverse_graph(graph, direction=Direction.BACKWARD))

        # Should include all nodes
        assert len(result) == 4
        result_indices = [graph.nodes.index(node) for node in result]

        # Both B and D should be starting points (no outgoing edges)
        first_two = result_indices[:2]
        assert {name_to_idx["B"], name_to_idx["D"]}.issubset(set(first_two))

        # All nodes should be included
        assert set(result_indices) == {0, 1, 2, 3}

    def test_custom_start_nodes(self):
        """Test BFS traversal with custom starting nodes."""
        analyzer = SimpleAnalyzer()
        graph, name_to_idx = _create_simple_linear_graph()

        # Start from node C
        start_nodes = [name_to_idx["C"]]
        result = list(
            analyzer.bfs_traverse_graph(graph, direction=Direction.FORWARD, start_nodes=start_nodes)
        )

        # Should start from C and reach D
        assert len(result) >= 2  # At least C and D
        result_indices = [graph.nodes.index(node) for node in result]

        # C should be first
        assert result_indices[0] == name_to_idx["C"]

        # D should be reachable
        assert name_to_idx["D"] in result_indices

    def test_custom_start_nodes_backward(self):
        """Test backward BFS traversal with custom starting nodes."""
        analyzer = SimpleAnalyzer()
        graph, name_to_idx = _create_simple_linear_graph()

        # Start from node B
        start_nodes = [name_to_idx["B"]]
        result = list(
            analyzer.bfs_traverse_graph(
                graph, direction=Direction.BACKWARD, start_nodes=start_nodes
            )
        )

        # Should start from B and reach A
        assert len(result) >= 2  # At least B and A
        result_indices = [graph.nodes.index(node) for node in result]

        # B should be first
        assert result_indices[0] == name_to_idx["B"]

        # A should be reachable
        assert name_to_idx["A"] in result_indices

    def test_invalid_start_nodes(self):
        """Test BFS traversal with invalid starting node indices."""
        analyzer = SimpleAnalyzer()
        graph, name_to_idx = _create_simple_linear_graph()

        # Use invalid indices
        start_nodes = [999, -1]  # Out of bounds
        result = list(
            analyzer.bfs_traverse_graph(graph, direction=Direction.FORWARD, start_nodes=start_nodes)
        )

        # Should still include all nodes (fallback behavior)
        assert len(result) == 4

    def test_direction_both(self):
        """Test BFS traversal with BOTH direction."""
        analyzer = SimpleAnalyzer()
        graph, name_to_idx = _create_simple_linear_graph()

        result = list(analyzer.bfs_traverse_graph(graph, direction=Direction.BOTH))

        # Should include all nodes
        assert len(result) == 4
        result_indices = [graph.nodes.index(node) for node in result]
        assert set(result_indices) == {0, 1, 2, 3}

    def test_cycle_handling_no_infinite_loop(self):
        """Test that cycles don't cause infinite loops."""
        analyzer = SimpleAnalyzer()
        graph, name_to_idx = _create_graph_with_sccs()

        # Even with cycles (B <-> C), should terminate and visit each node once
        result = list(analyzer.bfs_traverse_graph(graph, direction=Direction.FORWARD))

        assert len(result) == 4
        # Each node should appear exactly once
        result_indices = [graph.nodes.index(node) for node in result]
        assert len(set(result_indices)) == 4  # All unique

    def test_scc_ordering_consistency(self):
        """Test that SCC-based traversal respects topological ordering."""
        analyzer = SimpleAnalyzer()
        graph, name_to_idx = _create_graph_with_sccs()

        result = list(analyzer.bfs_traverse_graph(graph, direction=Direction.FORWARD))
        result_indices = [graph.nodes.index(node) for node in result]

        # A (SCC 0) should come before B,C (SCC 1)
        a_pos = result_indices.index(name_to_idx["A"])
        b_pos = result_indices.index(name_to_idx["B"])
        c_pos = result_indices.index(name_to_idx["C"])
        d_pos = result_indices.index(name_to_idx["D"])

        assert a_pos < b_pos
        assert a_pos < c_pos

        # B,C (SCC 1) should come before D (SCC 2)
        assert b_pos < d_pos
        assert c_pos < d_pos

    def test_determine_starting_nodes_no_scc(self):
        """Test _determine_starting_nodes method without SCCs."""
        analyzer = SimpleAnalyzer()
        graph, name_to_idx = _create_simple_linear_graph()

        # Build adjacency list for forward direction
        from collections import defaultdict

        adj = defaultdict(list)
        for edge in graph.edges:
            adj[edge.src].append(edge.dst)

        # Forward direction should start from A (no incoming edges)
        starting_nodes = analyzer._determine_starting_nodes(graph, Direction.FORWARD, adj)
        assert name_to_idx["A"] in starting_nodes

        # Backward direction should start from D (no outgoing edges)
        starting_nodes = analyzer._determine_starting_nodes(graph, Direction.BACKWARD, adj)
        assert name_to_idx["D"] in starting_nodes

    def test_determine_starting_nodes_with_scc(self):
        """Test _determine_starting_nodes method with SCCs."""
        analyzer = SimpleAnalyzer()
        graph, name_to_idx = _create_graph_with_sccs()

        # Build adjacency list for forward direction
        from collections import defaultdict

        adj = defaultdict(list)
        for edge in graph.edges:
            adj[edge.src].append(edge.dst)

        # Forward direction should start from SCC 0 (A)
        starting_nodes = analyzer._determine_starting_nodes(graph, Direction.FORWARD, adj)
        assert name_to_idx["A"] in starting_nodes

        # Backward direction should start from SCC 2 (D)
        starting_nodes = analyzer._determine_starting_nodes(graph, Direction.BACKWARD, adj)
        assert name_to_idx["D"] in starting_nodes


if __name__ == "__main__":
    pytest.main([__file__])
