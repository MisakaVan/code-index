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


def _create_complex_scc_graph() -> tuple[CallGraph, dict[str, int]]:
    """Create a complex call graph with multiple SCCs.

    Structure:
    - SCC A: a1 ↔ a2
    - SCC B: b1 → b2 → b3 → b1 (cycle)
    - SCC C: c1 ↔ c2
    - Connections: a1 → b1, b1 → c1

    Expected SCC ordering: A → B → C
    """
    # Create nodes
    a1 = PureDefinition(location=_loc("complex.py", 10))  # index 0
    a2 = PureDefinition(location=_loc("complex.py", 20))  # index 1
    b1 = PureDefinition(location=_loc("complex.py", 30))  # index 2
    b2 = PureDefinition(location=_loc("complex.py", 40))  # index 3
    b3 = PureDefinition(location=_loc("complex.py", 50))  # index 4
    c1 = PureDefinition(location=_loc("complex.py", 60))  # index 5
    c2 = PureDefinition(location=_loc("complex.py", 70))  # index 6

    nodes = [a1, a2, b1, b2, b3, c1, c2]
    owners = [
        Function(name="a1"),
        Function(name="a2"),
        Function(name="b1"),
        Function(name="b2"),
        Function(name="b3"),
        Function(name="c1"),
        Function(name="c2"),
    ]

    # Create edges
    edges = [
        # SCC A: a1 ↔ a2
        CallEdge(src=0, dst=1, kind=EdgeKind.MUST),  # a1 → a2
        CallEdge(src=1, dst=0, kind=EdgeKind.MUST),  # a2 → a1
        # SCC B: b1 → b2 → b3 → b1
        CallEdge(src=2, dst=3, kind=EdgeKind.MUST),  # b1 → b2
        CallEdge(src=3, dst=4, kind=EdgeKind.MUST),  # b2 → b3
        CallEdge(src=4, dst=2, kind=EdgeKind.MUST),  # b3 → b1
        # SCC C: c1 ↔ c2
        CallEdge(src=5, dst=6, kind=EdgeKind.MUST),  # c1 → c2
        CallEdge(src=6, dst=5, kind=EdgeKind.MUST),  # c2 → c1
        # Inter-SCC connections
        CallEdge(src=0, dst=2, kind=EdgeKind.MUST),  # a1 → b1
        CallEdge(src=2, dst=5, kind=EdgeKind.MUST),  # b1 → c1
    ]

    # Define SCCs
    sccs = [
        [0, 1],  # SCC 0: a1, a2
        [2, 3, 4],  # SCC 1: b1, b2, b3
        [5, 6],  # SCC 2: c1, c2
    ]

    # SCC edges: SCC0 → SCC1, SCC1 → SCC2
    scc_edges = [(0, 1), (1, 2)]

    graph = CallGraph(
        nodes=nodes,
        owners=owners,
        edges=edges,
        sccs=sccs,
        scc_edges=scc_edges,
        unresolved=[],
    )

    name_to_idx = {"a1": 0, "a2": 1, "b1": 2, "b2": 3, "b3": 4, "c1": 5, "c2": 6}
    return graph, name_to_idx


class TestComplexSCCTraversal:
    """Test BFS traversal on complex SCC structures."""

    def test_complex_scc_forward_traversal(self):
        """Test forward BFS traversal respects SCC ordering A→B→C."""
        analyzer = SimpleAnalyzer()
        graph, name_to_idx = _create_complex_scc_graph()

        result = list(analyzer.bfs_traverse_graph(graph, direction=Direction.FORWARD))
        result_indices = [graph.nodes.index(node) for node in result]

        # Should visit all 7 nodes
        assert len(result) == 7
        assert set(result_indices) == {0, 1, 2, 3, 4, 5, 6}

        # Find positions of each SCC's nodes
        scc_a_positions = [result_indices.index(i) for i in [0, 1]]  # a1, a2
        scc_b_positions = [result_indices.index(i) for i in [2, 3, 4]]  # b1, b2, b3
        scc_c_positions = [result_indices.index(i) for i in [5, 6]]  # c1, c2

        # Check that the FIRST node from each SCC appears in correct order
        # (BFS may interleave, but first appearance should be in SCC order)
        first_scc_a = min(scc_a_positions)
        first_scc_b = min(scc_b_positions)
        first_scc_c = min(scc_c_positions)

        assert first_scc_a < first_scc_b  # First A node before first B node
        assert first_scc_b < first_scc_c  # First B node before first C node

        # Should start from SCC A (in-degree 0)
        assert result_indices[0] in [0, 1]  # Either a1 or a2

    def test_complex_scc_backward_traversal(self):
        """Test backward BFS traversal respects reverse SCC ordering C→B→A."""
        analyzer = SimpleAnalyzer()
        graph, name_to_idx = _create_complex_scc_graph()

        result = list(analyzer.bfs_traverse_graph(graph, direction=Direction.BACKWARD))
        result_indices = [graph.nodes.index(node) for node in result]

        # Should visit all 7 nodes
        assert len(result) == 7
        assert set(result_indices) == {0, 1, 2, 3, 4, 5, 6}

        # Find positions of each SCC's nodes
        scc_a_positions = [result_indices.index(i) for i in [0, 1]]  # a1, a2
        scc_b_positions = [result_indices.index(i) for i in [2, 3, 4]]  # b1, b2, b3
        scc_c_positions = [result_indices.index(i) for i in [5, 6]]  # c1, c2

        # Check that the FIRST node from each SCC appears in reverse order
        first_scc_a = min(scc_a_positions)
        first_scc_b = min(scc_b_positions)
        first_scc_c = min(scc_c_positions)

        assert first_scc_c < first_scc_b  # First C node before first B node
        assert first_scc_b < first_scc_a  # First B node before first A node

        # Should start from SCC C (out-degree 0)
        assert result_indices[0] in [5, 6]  # Either c1 or c2

    def test_complex_scc_start_from_b2(self):
        """Test BFS traversal starting from specific node b2 in SCC B."""
        analyzer = SimpleAnalyzer()
        graph, name_to_idx = _create_complex_scc_graph()

        # Start from b2 (index 3)
        start_nodes = [name_to_idx["b2"]]

        # Forward traversal from b2
        result_forward = list(
            analyzer.bfs_traverse_graph(graph, direction=Direction.FORWARD, start_nodes=start_nodes)
        )
        result_forward_indices = [graph.nodes.index(node) for node in result_forward]

        # Should start with b2
        assert result_forward_indices[0] == name_to_idx["b2"]

        # Should be able to reach b3 and b1 (within same SCC)
        assert name_to_idx["b3"] in result_forward_indices
        assert name_to_idx["b1"] in result_forward_indices

        # Should be able to reach c1 and c2 (downstream SCC)
        assert name_to_idx["c1"] in result_forward_indices
        assert name_to_idx["c2"] in result_forward_indices

        # Should include all nodes eventually
        assert len(result_forward) == 7

        # Backward traversal from b2
        result_backward = list(
            analyzer.bfs_traverse_graph(
                graph, direction=Direction.BACKWARD, start_nodes=start_nodes
            )
        )
        result_backward_indices = [graph.nodes.index(node) for node in result_backward]

        # Should start with b2
        assert result_backward_indices[0] == name_to_idx["b2"]

        # Should be able to reach b1 and b3 (within same SCC)
        assert name_to_idx["b1"] in result_backward_indices
        assert name_to_idx["b3"] in result_backward_indices

        # Should be able to reach a1 and a2 (upstream SCC)
        assert name_to_idx["a1"] in result_backward_indices
        assert name_to_idx["a2"] in result_backward_indices

        # Should include all nodes eventually
        assert len(result_backward) == 7

    def test_complex_scc_internal_cycles(self):
        """Test that cycles within SCCs are handled correctly."""
        analyzer = SimpleAnalyzer()
        graph, name_to_idx = _create_complex_scc_graph()

        # Start from b1 and ensure we can reach all nodes in SCC B
        start_nodes = [name_to_idx["b1"]]
        result = list(
            analyzer.bfs_traverse_graph(graph, direction=Direction.FORWARD, start_nodes=start_nodes)
        )
        result_indices = [graph.nodes.index(node) for node in result]

        # Should visit each node exactly once (no infinite loop)
        assert len(result) == 7
        assert len(set(result_indices)) == 7  # All unique

        # All nodes in SCC B should be reachable from b1
        scc_b_nodes = {name_to_idx["b1"], name_to_idx["b2"], name_to_idx["b3"]}
        assert scc_b_nodes.issubset(set(result_indices))


if __name__ == "__main__":
    pytest.main([__file__])
