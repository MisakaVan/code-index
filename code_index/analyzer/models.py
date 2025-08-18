"""Analyzer-level Pydantic models for call graph construction and queries.

These models provide a definition-level (PureDefinition) call graph representation
and supporting options/results for analysis and path finding. They are designed
to be serialization-friendly and stable across analyzer implementations.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from ..models import (
    Function,
    Method,
    PureDefinition,
    PureReference,
    Symbol,
    SymbolDefinition,
)

__all__ = [
    # call-graph related
    "EdgeKind",
    "Direction",
    "CallEdge",
    "CallGraphStats",
    "UnresolvedCall",
    "CallGraph",
    "GraphConstructOptions",
    # find-path related
    "PathReturnMode",
    "IntraSCCStrategy",
    "NodePath",
    "SCCPath",
    "HybridSegment",
    "HybridPath",
    "FindPathsResult",
]


class EdgeKind(StrEnum):
    """Kinds of call edges.

    MUST: single concrete target (e.g., callee symbol has exactly one definition).
    MAY:  potential targets when overload/dispatch resolution is imprecise.
    """

    MUST = "must"
    """Single concrete target; call is bound to a unique callee definition."""
    MAY = "may"
    """Potential target(s); multiple candidate definitions may be called."""


class Direction(StrEnum):
    """Graph traversal direction."""

    FORWARD = "forward"
    """Edges follow call direction (caller -> callee)."""
    BACKWARD = "backward"
    """Edges reversed to show callers (callee -> caller)."""
    BOTH = "both"
    """Include both forward and backward traversals."""


class CallEdge(BaseModel):
    """An edge in the call graph referencing node indices."""

    src: int
    """Index into CallGraph.nodes for the caller definition."""

    dst: int
    """Index into CallGraph.nodes for the callee definition."""

    kind: EdgeKind = EdgeKind.MAY
    """Edge certainty kind (must/may)."""


class CallGraphStats(BaseModel):
    """Basic statistics of the graph."""

    num_nodes: int
    """Total number of nodes (definitions) in the graph."""

    num_edges: int
    """Total number of directed edges in the graph."""

    unresolved_calls: int = 0
    """Number of unresolved calls recorded during build."""

    build_seconds: float | None = None
    """Total time spent building the graph in seconds, if measured."""


class UnresolvedCall(BaseModel):
    """A call that couldn't be resolved to concrete callee definitions."""

    caller_def: PureDefinition
    """The definition from which the call originates."""

    via_symbol: Symbol
    """The symbol referenced at the call site."""

    callsites: list[PureReference] = Field(default_factory=list)
    """All call-sites in caller_def that contributed to this unresolved record."""

    reason: str = ""
    """Why this call is unresolved (e.g., "no_definitions_found", "not_expanded")."""


class CallGraph(BaseModel):
    """Definition-level call graph.

    Nodes are PureDefinition objects. Edges reference node indices for compact
    and stable serialization. SCCs and their DAG are represented by integer ids.
    """

    nodes: list[PureDefinition] = Field(default_factory=list)
    """All definition nodes included in the graph."""

    edges: list[CallEdge] = Field(default_factory=list)
    """Directed edges between definition nodes (src -> dst)."""

    owners: list[Symbol] = Field(default_factory=list)
    """Owner symbol for each node, aligned with ``nodes`` by index."""

    # SCCs: each SCC is a list of node indices; scc_edges are edges between SCC ids
    sccs: list[list[int]] = Field(default_factory=list)
    """List of SCCs, each as a list of node indices."""

    scc_edges: list[tuple[int, int]] = Field(default_factory=list)
    """Edges between SCCs represented by (from_scc_id, to_scc_id)."""

    unresolved: list[UnresolvedCall] = Field(default_factory=list)
    """Unresolved or pruned calls during graph construction."""

    stats: CallGraphStats | None = None
    """Optional graph statistics and build timings."""


class GraphConstructOptions(BaseModel):
    """Options controlling call graph construction and pruning behavior."""

    expand_calls: bool = True
    """If True, expand each call-site to all possible callee definitions (may-edges).
    If False, do not add edges for ambiguous calls and record them as unresolved."""

    direction: Direction = Direction.FORWARD
    """Traversal/build direction for graph construction and pruning."""

    entrypoints: list[PureDefinition] | None = None
    """Optional seed definitions; restrict graph to nodes reachable from them."""

    compute_scc: bool = True
    """Whether to compute SCCs and the SCC-DAG for the resulting graph."""


class PathReturnMode(StrEnum):
    """Return shape for find_paths results."""

    NODE = "node"  # list of PureDefinition
    """Return node-level paths (lists of PureDefinition)."""

    SCC = "scc"  # list of SCC ids
    """Return SCC-level paths (lists of SCC ids in the SCC-DAG)."""

    HYBRID = "hybrid"  # SCC segments with optional expanded node sequences
    """Return a mix of SCC segments optionally expanded to node sequences."""


class IntraSCCStrategy(StrEnum):
    """Strategy to expand paths within a single SCC when SCC-aware search is used."""

    NONE = "none"
    """Do not expand inside SCC; keep SCC-level representation only."""

    SHORTEST = "shortest"
    """Within an SCC, expand to one shortest path between boundary nodes."""

    BOUNDED_ENUMERATE = "bounded_enumerate"
    """Enumerate multiple paths inside SCC under a step/branching cap."""


class NodePath(BaseModel):
    """A path represented by concrete definition nodes (by value)."""

    nodes: list[SymbolDefinition]
    """Sequence of definition symbol+location along the path."""

    def __str__(self) -> str:
        parts: list[str] = []
        for sd in self.nodes:
            sym = sd.symbol
            if isinstance(sym, Method):
                parts.append(f"{(sym.class_name + '.') if sym.class_name else ''}{sym.name}")
            elif isinstance(sym, Function):
                parts.append(sym.name)
            else:
                parts.append(getattr(sym, "name", str(sym)))
        return "->".join(parts)


class SCCPath(BaseModel):
    """A path represented as a sequence of SCC ids in the SCC-DAG."""

    scc_ids: list[int]
    """Sequence of SCC ids along the path within the SCC-DAG."""

    def __str__(self) -> str:
        if not self.scc_ids:
            return "SCC[]"
        return "->".join(f"SCC[{i}]" for i in self.scc_ids)


class HybridSegment(BaseModel):
    """One segment of a hybrid path: an SCC and optional expanded node sequence inside it."""

    scc_id: int
    """The SCC id for this segment."""

    nodes: list[SymbolDefinition] | None = None
    """Optional node sequence expanded within this SCC for this segment."""


class HybridPath(BaseModel):
    """A path mixing SCC-level and node-level views."""

    segments: list[HybridSegment]
    """Ordered SCC segments that compose this path."""

    def __str__(self) -> str:
        parts: list[str] = []
        for seg in self.segments:
            head = f"SCC[{seg.scc_id}]"
            if seg.nodes:
                names: list[str] = []
                for sd in seg.nodes:
                    sym = sd.symbol
                    if isinstance(sym, Method):
                        names.append(
                            f"{(sym.class_name + '.') if sym.class_name else ''}{sym.name}"
                        )
                    elif isinstance(sym, Function):
                        names.append(sym.name)
                    else:
                        names.append(getattr(sym, "name", str(sym)))
                parts.append(f"{head}({'->'.join(names)})")
            else:
                parts.append(head)
        return "->".join(parts)


class FindPathsResult(BaseModel):
    """Result envelope for find_paths to make return type explicit and stable."""

    mode: PathReturnMode
    """Indicates which path representation is used by ``paths`` (node/scc/hybrid)."""

    paths: list[NodePath | SCCPath | HybridPath] = Field(default_factory=list)
    """The returned paths in the representation specified by ``mode``."""
