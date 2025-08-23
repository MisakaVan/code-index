"""Pydantic models for the MCP server API."""

from pydantic import BaseModel, Field

from code_index.analyzer.models import CallGraphStats
from code_index.models import PureDefinition, Symbol


class AllSymbolsResponse(BaseModel):
    """Response model for listing all symbols."""

    symbols: list[Symbol] = Field(
        ..., description="A sorted list of all unique Symbol symbols found in the index."
    )


class GetSubgraphRequest(BaseModel):
    """Request model for getting a subgraph from specific root definitions."""

    roots: list[PureDefinition] = Field(
        ..., description="List of root definitions to start the subgraph from"
    )
    depth: int = Field(default=5, description="Maximum depth to traverse from the root definitions")


class FindPathsRequest(BaseModel):
    """Request model for finding paths between two definitions."""

    src: PureDefinition = Field(..., description="Source definition")
    dst: PureDefinition = Field(..., description="Destination definition")
    k: int = Field(default=3, description="Maximum number of paths to find")


class SCCDetail(BaseModel):
    """Details about a strongly connected component."""

    scc_id: int = Field(..., description="The ID of the SCC")
    size: int = Field(..., description="Number of nodes in this SCC")
    nodes: list[PureDefinition] = Field(
        ..., description="Sample nodes in this SCC (limited to first 5)"
    )


class SCCOverview(BaseModel):
    """Overview of all SCCs in the call graph."""

    count: int = Field(..., description="Total number of SCCs")
    details: list[SCCDetail] = Field(..., description="Details for each SCC")


class GraphOverviewResponse(BaseModel):
    """Response model for call graph overview."""

    stats: CallGraphStats | None = Field(None, description="Graph statistics")
    scc_overview: SCCOverview = Field(..., description="SCC information")
    entrypoints: list[PureDefinition] = Field(..., description="Entry point definitions (up to 10)")
    endpoints: list[PureDefinition] = Field(..., description="End point definitions (up to 10)")


class TopologicalOrderResponse(BaseModel):
    """Response model for topological order of definitions."""

    definitions: list[PureDefinition] = Field(..., description="Definitions in topological order")
