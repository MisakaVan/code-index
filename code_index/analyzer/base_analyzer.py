"""Base class for index analyzers.

Index analyzers implement functionality to analyze code and extract
call-chains, call-graphs, and other relevant information from code
bases. They are used to process source code and generate
representations that can be queried or visualized.
"""

from abc import ABC, abstractmethod
from typing import Sequence

from ..index import BaseIndex
from .models import (
    CallGraph,
    FindPathsResult,
    GraphConstructOptions,
    IntraSCCStrategy,
    PathReturnMode,
)


class BaseAnalyzer(ABC):
    """Base class for index analyzers.

    Index analyzers implement functionality to analyze code and extract
    call-chains, call-graphs, and other relevant information from code
    bases. They are used to process source code and generate
    representations that can be queried or visualized.
    """

    def __init__(self): ...

    @abstractmethod
    def get_call_graph(
        self, index: BaseIndex, options: GraphConstructOptions | None = None
    ) -> CallGraph:
        """Build a definition-level call graph for the given index.

        The returned graph uses PureDefinition nodes and directed edges representing
        calls among definitions. SCCs (Strongly Connected Components) can be computed
        to provide an SCC-DAG for path planning and visualization.

        Args:
            index: The source index that provides definitions and call references.
            options: Optional analyzer options controlling bind policy, fanout cap,
                entry points, direction, and SCC computation behavior.

        Returns:
            CallGraph: A Pydantic model that can be serialized and consumed by
                downstream tooling.
        """
        pass

    @abstractmethod
    def get_subgraph(
        self,
        graph: CallGraph,
        roots: Sequence[int] | None = None,
        *,
        depth: int | None = None,
        include_reverse: bool = False,
    ) -> CallGraph:
        """Return a pruned subgraph rooted at the given node indices.

        Nodes are addressed by their integer indices in ``graph.nodes`` to avoid
        heavy copying/comparison of definition payloads. If ``roots`` is None,
        returns the original graph (or a shallow-copied equivalent) possibly
        pruned by depth.

        Args:
            graph: The full call graph.
            roots: One or more node indices in ``graph.nodes`` as starting points.
            depth: Optional maximum traversal depth from the roots.
            include_reverse: If True, include reverse edges (callers) when traversing.

        Returns:
            A new CallGraph instance that only contains the reachable nodes/edges
            under the specified constraints.
        """
        pass

    @abstractmethod
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
        """Find up to ``k`` paths from ``src_idx`` to ``dst_idx`` in the call graph.

        When ``scc_aware`` is True, path planning is performed on the SCC-DAG first
        to avoid cycling inside strongly connected components. Then, for intra-SCC
        segments, the method expands according to ``intra_scc`` strategy.

        Args:
            graph: The call graph built by :meth:`get_call_graph`.
            src_idx: Source node index in ``graph.nodes``.
            dst_idx: Destination node index in ``graph.nodes``.
            k: Maximum number of paths to return.
            max_depth: Optional overall depth cap for node-level expansion.
            scc_aware: If True, operate on SCC-DAG first to avoid loops.
            return_mode: Path return mode (node/scc/hybrid).
            intra_scc: Strategy within one SCC (none/shortest/bounded_enumerate).
            intra_scc_step_cap: Limit the number of steps explored within an SCC.

        Returns:
            FindPathsResult: Paths in the requested representation mode.
        """
        pass
