"""Pydantic models for the MCP server API."""

from pydantic import BaseModel, Field

from code_index.models import Symbol


class AllSymbolsResponse(BaseModel):
    """Response model for listing all symbols."""

    symbols: list[Symbol] = Field(
        ..., description="A sorted list of all unique Symbol symbols found in the index."
    )
