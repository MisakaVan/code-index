"""A minimal, pragmatic analyzer implementation.

SimpleAnalyzer builds a definition-level call graph from a BaseIndex and
offers basic subgraph extraction and path finding utilities.
"""

from __future__ import annotations

from collections import defaultdict, deque
from time import perf_counter
from typing import Sequence

from ..index import BaseIndex
from ..models import Definition, PureDefinition, Symbol
from .base_analyzer import BaseAnalyzer
from .models import (
    CallEdge,
    CallGraph,
    CallGraphStats,
    Direction,
    EdgeKind,
    FindPathsResult,
    GraphConstructOptions,
    HybridPath,
    HybridSegment,
    IntraSCCStrategy,
    NodePath,
    PathReturnMode,
    SCCPath,
)


class SimpleAnalyzer(BaseAnalyzer):
    """A straightforward analyzer that expands calls based on index contents."""

    def get_call_graph(
        self, index: BaseIndex, options: GraphConstructOptions | None = None
    ) -> CallGraph:
        opts = options or GraphConstructOptions()

        start_ts = perf_counter()

        # 1) Collect all definition nodes and their owner symbols
        nodes: list[PureDefinition] = []
        owners: list[Symbol] = []
        index_of: dict[PureDefinition, int] = {}
        for symbol, info in index.items():
            for d in info.definitions:
                pd = d.to_pure()
                if pd not in index_of:
                    index_of[pd] = len(nodes)
                    nodes.append(pd)
                    owners.append(symbol)

        # 2) Create edges by expanding calls
        edges: list[CallEdge] = []
        unresolved: list[dict[str, object]] = []

        def add_edge(src_pd: PureDefinition, dst_pd: PureDefinition, kind: EdgeKind):
            # Ensure nodes exist
            if dst_pd not in index_of:
                # Find the symbol for this definition by looking through the index
                dst_symbol = None
                for symbol, info in index.items():
                    for d in info.definitions:
                        if d.to_pure() == dst_pd:
                            dst_symbol = symbol
                            break
                    if dst_symbol:
                        break
                if dst_symbol:
                    index_of[dst_pd] = len(nodes)
                    nodes.append(dst_pd)
                    owners.append(dst_symbol)
            if src_pd not in index_of:
                # Find the symbol for this definition by looking through the index
                src_symbol = None
                for symbol, info in index.items():
                    for d in info.definitions:
                        if d.to_pure() == src_pd:
                            src_symbol = symbol
                            break
                    if src_symbol:
                        break
                if src_symbol:
                    index_of[src_pd] = len(nodes)
                    nodes.append(src_pd)
                    owners.append(src_symbol)
            edges.append(CallEdge(src=index_of[src_pd], dst=index_of[dst_pd], kind=kind))

        # Build a map for faster lookup of definitions of a symbol
        def_defs_cache: dict[Symbol, list[Definition]] = {}

        for _, info in index.items():
            for d in info.definitions:
                caller_pd = d.to_pure()
                for symref in d.calls:
                    callee = symref.symbol
                    if callee not in def_defs_cache:
                        def_defs_cache[callee] = list(index.get_definitions(callee))

                    targets = def_defs_cache[callee]
                    if not targets:
                        # unresolved callee
                        unresolved.append(
                            {
                                "caller_def": caller_pd,
                                "via_symbol": callee,
                                "callsites": [symref.reference],
                                "reason": "no_definitions_found",
                            }
                        )
                        continue

                    if len(targets) == 1:
                        add_edge(caller_pd, targets[0].to_pure(), EdgeKind.MUST)
                    else:
                        if opts.expand_calls:
                            for td in targets:
                                add_edge(caller_pd, td.to_pure(), EdgeKind.MAY)
                        else:
                            unresolved.append(
                                {
                                    "caller_def": caller_pd,
                                    "via_symbol": callee,
                                    "callsites": [symref.reference],
                                    "reason": "ambiguous_targets",
                                }
                            )

        # 3) Apply direction (forward/backward/both) at edge level
        if opts.direction == Direction.BACKWARD:
            edges = [CallEdge(src=e.dst, dst=e.src, kind=e.kind) for e in edges]
        elif opts.direction == Direction.BOTH:
            edges = edges + [CallEdge(src=e.dst, dst=e.src, kind=e.kind) for e in edges]

        # 4) Optional entrypoint pruning
        if opts.entrypoints:
            keep_mask = self._reachable_mask(nodes, edges, opts.entrypoints, include_reverse=False)
            nodes, owners, index_of, edges = self._prune_to_mask(nodes, owners, edges, keep_mask)

        # 5) Compute SCCs (optional)
        sccs, scc_edges = ([], [])
        if opts.compute_scc:
            scc_id, sccs = self._tarjan_scc(nodes, edges)
            scc_edges = self._scc_edges(edges, scc_id)

        stats = CallGraphStats(
            num_nodes=len(nodes),
            num_edges=len(edges),
            unresolved_calls=len(unresolved),
            build_seconds=perf_counter() - start_ts,
        )

        # Convert unresolved dicts to UnresolvedCall models
        from .models import UnresolvedCall  # local import to avoid cycle concerns

        unresolved_models = [
            UnresolvedCall(
                caller_def=it["caller_def"],  # type: ignore[arg-type]
                via_symbol=it["via_symbol"],  # type: ignore[arg-type]
                callsites=it["callsites"],  # type: ignore[arg-type]
                reason=it["reason"],  # type: ignore[arg-type]
            )
            for it in unresolved
        ]

        return CallGraph(
            nodes=nodes,
            owners=owners,
            edges=edges,
            sccs=sccs,
            scc_edges=scc_edges,
            unresolved=unresolved_models,
            stats=stats,
        )

    def get_subgraph(
        self,
        graph: CallGraph,
        roots: Sequence[int] | None = None,
        *,
        depth: int | None = None,
        include_reverse: bool = False,
    ) -> CallGraph:
        if roots is None or len(roots) == 0:
            if depth is None and not include_reverse:
                return graph

        keep_mask = self._reachable_mask(
            graph.nodes,
            graph.edges,
            [graph.nodes[r] for r in roots] if roots else None,
            include_reverse=include_reverse,
            depth=depth,
        )
        nodes, owners, index_of, edges = self._prune_to_mask(
            graph.nodes, graph.owners, graph.edges, keep_mask
        )

        # recompute SCCs for the subgraph
        scc_id, sccs = self._tarjan_scc(nodes, edges)
        scc_edges = self._scc_edges(edges, scc_id)

        stats = CallGraphStats(
            num_nodes=len(nodes), num_edges=len(edges), unresolved_calls=len(graph.unresolved)
        )
        return CallGraph(
            nodes=nodes,
            owners=owners,
            edges=edges,
            sccs=sccs,
            scc_edges=scc_edges,
            unresolved=graph.unresolved,
            stats=stats,
        )

    def find_paths(
        self,
        graph: CallGraph,
        src_idx: int,
        dst_idx: int,
        *,
        k: int = 1,
        max_depth: int | None = None,
        scc_aware: bool = True,
        return_mode: PathReturnMode = PathReturnMode.NODE,
        intra_scc: IntraSCCStrategy = IntraSCCStrategy.SHORTEST,
        intra_scc_step_cap: int = 50,
    ) -> FindPathsResult:
        # adjacency
        adj: dict[int, list[int]] = defaultdict(list)
        for e in graph.edges:
            adj[e.src].append(e.dst)

        if return_mode == PathReturnMode.SCC:
            # Ensure SCCs available
            if not graph.sccs:
                _, sccs = self._tarjan_scc(graph.nodes, graph.edges)
            else:
                sccs = graph.sccs
            node_to_scc = {n: sid for sid, comp in enumerate(sccs) for n in comp}
            src_scc, dst_scc = node_to_scc.get(src_idx), node_to_scc.get(dst_idx)
            if src_scc is None or dst_scc is None:
                return FindPathsResult(mode=PathReturnMode.SCC, paths=[])
            dag_adj = defaultdict(list)
            for u, v in graph.scc_edges or self._scc_edges(graph.edges, node_to_scc):
                dag_adj[u].append(v)
            scc_paths = self._dfs_k_paths(dag_adj, src_scc, dst_scc, k=k, max_depth=max_depth)
            return FindPathsResult(
                mode=PathReturnMode.SCC,
                paths=[SCCPath(scc_ids=p) for p in scc_paths],
            )

        # For NODE and HYBRID, run node-level search; HYBRID will wrap as SCC segments w/o expansion.
        paths = self._dfs_k_paths(adj, src_idx, dst_idx, k=k, max_depth=max_depth)

        if return_mode == PathReturnMode.NODE:
            from ..models import SymbolDefinition  # local import

            return FindPathsResult(
                mode=PathReturnMode.NODE,
                paths=[
                    NodePath(
                        nodes=[
                            SymbolDefinition(symbol=graph.owners[i], definition=graph.nodes[i])
                            for i in p
                        ]
                    )
                    for p in paths
                ],
            )

        # HYBRID: represent each path as SCC segments without intra-SCC expansion for simplicity
        if not graph.sccs:
            _, sccs = self._tarjan_scc(graph.nodes, graph.edges)
        else:
            sccs = graph.sccs
        node_to_scc = {n: sid for sid, comp in enumerate(sccs) for n in comp}

        hybrid_paths: list[HybridPath] = []
        for p in paths:
            segments: list[HybridSegment] = []
            last_sid: int | None = None
            for node in p:
                sid = node_to_scc.get(node)
                if sid is None:
                    continue
                if last_sid != sid:
                    # For simplicity, we're not expanding nodes within SCC segments
                    # But if we wanted to, we would create SymbolDefinition objects here too
                    segments.append(HybridSegment(scc_id=sid, nodes=None))
                    last_sid = sid
            hybrid_paths.append(HybridPath(segments=segments))

        return FindPathsResult(mode=PathReturnMode.HYBRID, paths=hybrid_paths)

    # ---------- helpers ----------
    @staticmethod
    def _reachable_mask(
        nodes: list[PureDefinition],
        edges: list[CallEdge],
        entrypoints: Sequence[PureDefinition] | None,
        *,
        include_reverse: bool,
        depth: int | None = None,
    ) -> list[bool]:
        if not entrypoints:
            return [True] * len(nodes)
        index_of = {pd: i for i, pd in enumerate(nodes)}
        adj = defaultdict(list)
        radj = defaultdict(list)
        for e in edges:
            adj[e.src].append(e.dst)
            radj[e.dst].append(e.src)
        q: deque[tuple[int, int]] = deque()
        seen = set()
        for ep in entrypoints:
            if ep in index_of:
                i = index_of[ep]
                q.append((i, 0))
                seen.add(i)
        while q:
            u, d = q.popleft()
            if depth is not None and d >= depth:
                continue
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    q.append((v, d + 1))
            if include_reverse:
                for v in radj[u]:
                    if v not in seen:
                        seen.add(v)
                        q.append((v, d + 1))
        mask = [False] * len(nodes)
        for i in seen:
            mask[i] = True
        return mask

    @staticmethod
    def _prune_to_mask(
        nodes: list[PureDefinition], owners: list[Symbol], edges: list[CallEdge], mask: list[bool]
    ) -> tuple[list[PureDefinition], list[Symbol], dict[PureDefinition, int], list[CallEdge]]:
        new_indices = {}
        new_nodes: list[PureDefinition] = []
        new_owners: list[Symbol] = []
        for i, keep in enumerate(mask):
            if keep:
                new_indices[i] = len(new_nodes)
                new_nodes.append(nodes[i])
                new_owners.append(owners[i])
        # remap edges
        new_edges: list[CallEdge] = []
        for e in edges:
            if mask[e.src] and mask[e.dst]:
                new_edges.append(
                    CallEdge(src=new_indices[e.src], dst=new_indices[e.dst], kind=e.kind)
                )
        return new_nodes, new_owners, {pd: i for i, pd in enumerate(new_nodes)}, new_edges

    @staticmethod
    def _tarjan_scc(nodes: list[PureDefinition], edges: list[CallEdge]):
        n = len(nodes)
        adj = defaultdict(list)
        for e in edges:
            adj[e.src].append(e.dst)

        index = 0
        indices = [-1] * n
        lowlink = [0] * n
        onstack = [False] * n
        stack: list[int] = []
        sccs: list[list[int]] = []

        def strongconnect(v: int):
            nonlocal index
            indices[v] = index
            lowlink[v] = index
            index += 1
            stack.append(v)
            onstack[v] = True

            for w in adj[v]:
                if indices[w] == -1:
                    strongconnect(w)
                    lowlink[v] = min(lowlink[v], lowlink[w])
                elif onstack[w]:
                    lowlink[v] = min(lowlink[v], indices[w])

            if lowlink[v] == indices[v]:
                comp = []
                while True:
                    w = stack.pop()
                    onstack[w] = False
                    comp.append(w)
                    if w == v:
                        break
                sccs.append(comp)

        for v in range(n):
            if indices[v] == -1:
                strongconnect(v)

        node_to_scc = {}
        for sid, comp in enumerate(sccs):
            for v in comp:
                node_to_scc[v] = sid
        return node_to_scc, sccs

    @staticmethod
    def _scc_edges(edges: list[CallEdge], node_to_scc: dict[int, int]):
        pairs = set()
        for e in edges:
            su = node_to_scc[e.src]
            sv = node_to_scc[e.dst]
            if su != sv:
                pairs.add((su, sv))
        return list(pairs)

    @staticmethod
    def _dfs_k_paths(
        adj: dict[int, list[int]], src: int, dst: int, *, k: int, max_depth: int | None
    ):
        paths: list[list[int]] = []
        path: list[int] = []

        def dfs(u: int, depth: int):
            if len(paths) >= k:
                return
            if max_depth is not None and depth > max_depth:
                return
            path.append(u)
            if u == dst:
                paths.append(path.copy())
                path.pop()
                return
            for v in adj.get(u, []):
                if v in path:
                    # avoid cycles
                    continue
                dfs(v, depth + 1)
                if len(paths) >= k:
                    break
            path.pop()

        dfs(src, 0)
        return paths
