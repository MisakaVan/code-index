"""Pydantic models for the MCP server API."""

from pydantic import BaseModel, Field

from code_index.models import FunctionLike


class AllSymbolsResponse(BaseModel):
    """Response model for listing all symbols."""

    symbols: list[FunctionLike] = Field(
        ..., description="A sorted list of all unique FunctionLike symbols found in the index."
    )
