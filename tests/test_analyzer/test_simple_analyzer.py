from __future__ import annotations

from pathlib import Path

from code_index.analyzer.models import (
    CallGraph,
    Direction,
    EdgeKind,
    FindPathsResult,
    GraphConstructOptions,
    PathReturnMode,
)
from code_index.analyzer.simple_analyzer import SimpleAnalyzer
from code_index.index.impl.cross_ref_index import CrossRefIndex
from code_index.models import (
    CodeLocation,
    Definition,
    Function,
    PureDefinition,
    PureReference,
    SymbolReference,
)


def _loc(file: str, base: int) -> CodeLocation:
    return CodeLocation(
        file_path=Path(file),
        start_lineno=base,
        start_col=0,
        end_lineno=base,
        end_col=10,
        start_byte=base * 10,
        end_byte=base * 10 + 5,
    )


def _build_index(with_cycle: bool = False) -> tuple[CrossRefIndex, dict[str, PureDefinition]]:
    idx = CrossRefIndex()

    A = Function(name="A")
    B = Function(name="B")
    C = Function(name="C")
    D = Function(name="D")

    A_def = Definition(location=_loc("t.py", 10), calls=[])
    B_def = Definition(location=_loc("t.py", 20), calls=[])
    C_def = Definition(location=_loc("t.py", 30), calls=[])
    D_def1 = Definition(location=_loc("t.py", 40), calls=[])
    D_def2 = Definition(location=_loc("t.py", 50), calls=[])

    # Calls: A -> B, B -> C
    A_def = A_def.add_callee(
        SymbolReference(symbol=B, reference=PureReference(location=_loc("t.py", 11)))
    )
    B_def = B_def.add_callee(
        SymbolReference(symbol=C, reference=PureReference(location=_loc("t.py", 21)))
    )

    # Optional cycle: C -> A
    if with_cycle:
        C_def = C_def.add_callee(
            SymbolReference(symbol=A, reference=PureReference(location=_loc("t.py", 31)))
        )

    # Ambiguous: A -> D (two definitions)
    A_def = A_def.add_callee(
        SymbolReference(symbol=D, reference=PureReference(location=_loc("t.py", 12)))
    )

    # Populate index
    idx.add_definition(A, A_def)
    idx.add_definition(B, B_def)
    idx.add_definition(C, C_def)
    idx.add_definition(D, D_def1)
    idx.add_definition(D, D_def2)

    return idx, {
        "A": A_def.to_pure(),
        "B": B_def.to_pure(),
        "C": C_def.to_pure(),
        "D1": D_def1.to_pure(),
        "D2": D_def2.to_pure(),
    }


def _index_of(nodes: list[PureDefinition]) -> dict[PureDefinition, int]:
    return {pd: i for i, pd in enumerate(nodes)}


def test_get_call_graph_basic_unresolved_when_not_expanding():
    idx, defs = _build_index(with_cycle=False)
    analyzer = SimpleAnalyzer()
    graph: CallGraph = analyzer.get_call_graph(
        idx,
        GraphConstructOptions(expand_calls=False, direction=Direction.FORWARD, compute_scc=True),
    )

    io = _index_of(graph.nodes)
    # MUST edges: A->B, B->C
    assert (io[defs["A"]], io[defs["B"]], EdgeKind.MUST) in [
        (e.src, e.dst, e.kind) for e in graph.edges
    ]
    assert (io[defs["B"]], io[defs["C"]], EdgeKind.MUST) in [
        (e.src, e.dst, e.kind) for e in graph.edges
    ]

    # No edges to D defs when not expanding ambiguous
    d_targets = {(io.get(defs["A"]), io.get(defs["D1"])), (io.get(defs["A"]), io.get(defs["D2"]))}
    edge_pairs = {(e.src, e.dst) for e in graph.edges}
    assert not any(p in edge_pairs for p in d_targets)

    # One unresolved due to ambiguous D
    assert len(graph.unresolved) == 1


def test_get_call_graph_expand_calls_creates_may_edges():
    idx, defs = _build_index(with_cycle=False)
    analyzer = SimpleAnalyzer()
    graph = analyzer.get_call_graph(
        idx, GraphConstructOptions(expand_calls=True, direction=Direction.FORWARD, compute_scc=True)
    )
    io = _index_of(graph.nodes)

    # Edges to both D1 & D2 as MAY
    may_edges = {(e.src, e.dst) for e in graph.edges if e.kind == EdgeKind.MAY}
    assert (io[defs["A"]], io[defs["D1"]]) in may_edges
    assert (io[defs["A"]], io[defs["D2"]]) in may_edges

    # No unresolved for the ambiguous call when expanded
    # (Other unresolved should not exist in this setup)
    assert len(graph.unresolved) == 0


def test_direction_backward_reverses_edges():
    idx, defs = _build_index(with_cycle=False)
    analyzer = SimpleAnalyzer()
    graph = analyzer.get_call_graph(
        idx,
        GraphConstructOptions(expand_calls=False, direction=Direction.BACKWARD, compute_scc=False),
    )
    io = _index_of(graph.nodes)
    # Backward should include C->B and B->A
    assert (io[defs["C"]], io[defs["B"]]) in {(e.src, e.dst) for e in graph.edges}
    assert (io[defs["B"]], io[defs["A"]]) in {(e.src, e.dst) for e in graph.edges}


def test_entrypoint_pruning_limits_nodes():
    idx, defs = _build_index(with_cycle=False)
    analyzer = SimpleAnalyzer()
    graph = analyzer.get_call_graph(
        idx,
        GraphConstructOptions(
            expand_calls=False,
            direction=Direction.FORWARD,
            compute_scc=False,
            entrypoints=[defs["B"]],
        ),
    )
    # Only B and C should remain reachable from B in forward direction
    pds = set(graph.nodes)
    assert defs["B"] in pds and defs["C"] in pds
    assert defs["A"] not in pds


def test_scc_and_find_paths_node_scc_hybrid():
    idx, defs = _build_index(with_cycle=True)
    analyzer = SimpleAnalyzer()
    graph = analyzer.get_call_graph(
        idx,
        GraphConstructOptions(expand_calls=False, direction=Direction.FORWARD, compute_scc=True),
    )
    io = _index_of(graph.nodes)

    # Single SCC containing A,B,C
    assert len(graph.sccs) >= 1
    scc_with_abc = [
        comp for comp in graph.sccs if all(io[d] in comp for d in (defs["A"], defs["B"], defs["C"]))
    ]
    assert len(scc_with_abc) == 1
    scc_id_map = {n: sid for sid, comp in enumerate(graph.sccs) for n in comp}
    sid = scc_id_map[io[defs["A"]]]

    # NODE paths from A to C
    res_node: FindPathsResult = analyzer.find_paths(
        graph, io[defs["A"]], io[defs["C"]], k=1, return_mode=PathReturnMode.NODE
    )
    assert res_node.mode == PathReturnMode.NODE
    assert len(res_node.paths) >= 1
    # Check that the definitions match (extract the definition from SymbolDefinition)
    actual_defs = [sd.definition for sd in res_node.paths[0].nodes[:3]]
    assert [defs["A"], defs["B"], defs["C"]] == actual_defs

    # SCC paths from A to C (same SCC -> single id path)
    res_scc = analyzer.find_paths(
        graph, io[defs["A"]], io[defs["C"]], k=1, return_mode=PathReturnMode.SCC
    )
    assert res_scc.mode == PathReturnMode.SCC
    assert len(res_scc.paths) >= 1
    assert res_scc.paths[0].scc_ids[0] == sid

    # HYBRID returns SCC segments with intra-SCC paths
    res_hybrid = analyzer.find_paths(
        graph, io[defs["A"]], io[defs["C"]], k=1, return_mode=PathReturnMode.HYBRID
    )
    assert res_hybrid.mode == PathReturnMode.HYBRID
    assert len(res_hybrid.paths) >= 1
    assert res_hybrid.paths[0].segments[0].scc_id == sid

    # Verify that the segment contains the nodes within the SCC
    segment = res_hybrid.paths[0].segments[0]
    assert segment.nodes is not None
    assert len(segment.nodes) >= 3  # Should contain A, B, C

    # Check that the definitions match (extract the definition from SymbolDefinition)
    segment_defs = [sd.definition for sd in segment.nodes]
    assert defs["A"] in segment_defs
    assert defs["B"] in segment_defs
    assert defs["C"] in segment_defs
