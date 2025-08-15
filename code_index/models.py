"""Pydantic models for representing code elements and their relationships.

This module defines the core data structures used to model functions, methods,
references, definitions, and their relationships in a codebase.
"""

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, model_serializer

__all__ = [
    "CodeLocation",
    "Function",
    "Method",
    "FunctionLike",
    "SymbolReference",
    "PureReference",
    "Definition",
    "Reference",
    "SymbolDefinition",
    "PureDefinition",
    "FunctionLikeInfo",
    "IndexDataEntry",
    "IndexData",
]


class CodeLocation(BaseModel):
    """Represents a specific location in source code.

    Contains precise position information including line numbers, column positions,
    and byte offsets for a code element within a source file.
    """

    file_path: Path
    """Path to the source file containing this location."""
    start_lineno: int
    """Starting line number (1-based)."""
    start_col: int
    """Starting column number (0-based)."""
    end_lineno: int
    """Ending line number (1-based)."""
    end_col: int
    """Ending column number (0-based)."""
    start_byte: int
    """Byte offset in the file where the location starts (including)."""
    end_byte: int
    """Byte offset in the file where the location ends (not including)."""

    model_config = {"frozen": True}

    def __str__(self) -> str:
        """Return a string representation of the code location."""
        return f"CodeLocation({self.file_path}, {self.start_lineno}:{self.start_col}-{self.end_lineno}:{self.end_col}, {self.start_byte}-{self.end_byte})"


class SymbolType(StrEnum):
    """Enumeration of symbol types for code elements.

    This enum defines the types of symbols that can be represented in the codebase,
    such as functions, methods, classes, etc. It is used to categorize and identify
    different kinds of code elements.
    """

    UNSET = "unset"
    """An unset or unknown symbol type."""
    FUNCTION = "function"
    """A standalone function."""
    METHOD = "method"
    """A method bound to a class."""


class BaseSymbol(BaseModel):
    """Base class for all code symbols.

    This class makes sure that all symbols have a ``type`` discriminator field
    that won't be excluded from serialization (when exclude_defaults=True is set).
    """

    @model_serializer(mode="wrap")
    def serialize(self, nxt):
        dumped = nxt(self)
        # Ensure the type field is always present
        dumped["type"] = self.type.value
        return dumped


class Function(BaseSymbol):
    """Represents a standalone function in the codebase.

    A function is a callable code block that is not bound to any class.
    This includes module-level functions, nested functions, and lambda functions.
    """

    type: Literal[SymbolType.FUNCTION] = SymbolType.FUNCTION
    """Type discriminator for function."""
    name: str
    """The name of the function."""

    model_config = {"frozen": True}


class Method(BaseSymbol):
    """Represents a method bound to a class in the codebase.

    A method is a function that belongs to a class. The class_name may be None
    for method calls where the class context cannot be determined statically.
    """

    type: Literal[SymbolType.METHOD] = SymbolType.METHOD
    """Type discriminator for method."""
    name: str
    """The name of the method."""
    class_name: str | None
    """The name of the class the method belongs to. May be None for calls where the class context is not accessible or determinable."""

    model_config = {"frozen": True}


FunctionLike = Annotated[
    Function | Method,
    Field(discriminator="type", description="Discriminated union for function-like entities."),
]
"""Represents a function or method in the codebase. A discriminated union type that can be either a Function or a Method.

The discriminator field 'type' is used to determine which variant to deserialize to.
Pydantic automatically handles serialization and deserialization based on this field.

Example usage:

.. code-block:: python

    from pydantic import TypeAdapter

    # For standalone validation of FunctionLike objects
    funclike_adapter = TypeAdapter(FunctionLike)

    # Validate from dict
    func_data = {"type": "function", "name": "my_func"}
    function_obj = funclike_adapter.validate_python(func_data)

    # Validate from JSON
    method_json = '{"type": "method", "name": "my_method", "class_name": "MyClass"}'
    method_obj = funclike_adapter.validate_json(method_json)
"""


class PureReference(BaseModel):
    """A minimal, hashable fingerprint of a function or method reference.

    This class serves as a unique identifier containing only the essential
    location information needed to distinguish one reference from another.
    It acts as a fingerprint for the more comprehensive Reference class
    and is designed to be used as a dictionary key for fast lookups.

    The "Pure" designation indicates this contains only the core, immutable
    identity of a reference without any additional contextual information.
    """

    location: CodeLocation
    """The code location where the reference occurs."""

    model_config = {"frozen": True}


class PureDefinition(BaseModel):
    """A minimal, hashable fingerprint of a function or method definition.

    This class serves as a unique identifier containing only the essential
    location information needed to distinguish one definition from another.
    It acts as a fingerprint for the more comprehensive Definition class
    and is designed to be used as a dictionary key for fast lookups.

    The "Pure" designation indicates this contains only the core, immutable
    identity of a definition without any additional contextual information.
    """

    location: CodeLocation
    """The code location where the definition occurs."""

    model_config = {"frozen": True}


class SymbolReference(BaseModel):
    """Represents a reference to a function-like entity with context.

    This combines a function or method symbol with the specific reference location,
    providing full context about where and what is being referenced.
    """

    symbol: FunctionLike
    """The function or method being referenced."""
    reference: PureReference
    """The reference information including location."""

    model_config = {"frozen": True}


class SymbolDefinition(BaseModel):
    """Represents a definition of a function-like entity with context.

    This combines a function or method symbol with the specific definition information,
    providing full context about where and what is being defined.
    """

    symbol: FunctionLike
    """The function or method being defined."""
    definition: PureDefinition
    """The definition information including location."""

    model_config = {"frozen": True}


class Reference(BaseModel):
    """Extended reference information with additional contextual data.

    This class inherits from PureReference (which serves as its fingerprint)
    and adds optional contextual information about the reference. The design
    is extensible, allowing future additions of more reference-related data
    without breaking the core identification mechanism provided by PureReference.

    A reference occurs when a function or method is called, passed as an argument,
    or otherwise used in the code (but not where it's defined).
    """

    location: CodeLocation
    """The code location where the reference occurs."""

    called_by: list[SymbolDefinition] = Field(default_factory=list)
    """The definitions that call this reference, if applicable.

    Note this means "which definitions call this reference" rather than "which symbols call this reference?".
    Though there should be no more than one caller of a given call-site, we hold this as an iterable, because
    there are lambdas, closures, wrapped functions, and one call-site may be found inside the scope of multiple
    definitions.
    """

    model_config = {"frozen": True}

    def to_pure(self) -> PureReference:
        """Extract the pure fingerprint of this reference for use as a dictionary key.

        Returns:
            A PureReference containing only the location information,
            suitable for hashing and fast lookups.
        """
        return PureReference(location=self.location)

    @classmethod
    def from_pure(cls, pure_ref: PureReference) -> "Reference":
        """Create a Reference instance from a PureReference.

        This method allows creating a Reference instance with an empty context
        (no call sites) from a PureReference, which is useful for initializing
        references before additional context is added.

        Args:
            pure_ref (PureReference): The pure reference to convert.

        Returns:
            Reference: A new Reference instance with the same location as the PureReference.
        """
        return cls(location=pure_ref.location, called_by=[])

    def add_caller(self, caller: SymbolDefinition) -> "Reference":
        """Add a caller definition to this reference.

        This method allows adding a definition that call this reference.
        It ensures that the caller is added only if it is not already present.

        Args:
            caller:

        Returns:
            Reference: The updated Reference instance with the new caller(s) added.
        """
        if caller not in self.called_by:
            self.called_by.append(caller)
        return self

    def merge(self, other: "Reference") -> None:
        """Merge information about the same PureReference.

        This method allows merging additional contextual information from another Reference
        into this one, such as additional call sites or definitions that reference this location.

        Args:
            other (Reference): Another Reference instance with additional context to merge.

        Raises:
            ValueError: If the other reference does not have the same PureReference.
        """
        if self.location != other.location:  # equivalent to PureReference equality
            raise ValueError("Cannot merge references with different PureReference locations.")

        # Merge the call sites
        for caller in other.called_by:
            self.add_caller(caller)


class LLMNote(BaseModel):
    """Represents a note about a definition, generated by an LLM.

    This note may contain various fields that provide additional context or
    information about the definition, such as its purpose, usage, how the control
    flow works, or any other relevant details that can help understand the code.
    """

    description: str = Field(
        default="",
        description="A description of the definition, generated by an LLM. This may include what this "
        "function/method does, its purpose, what resources it manages, how the control flow switches according "
        "to different parameters, etc.",
    )
    potential_vulnerabilities: str = Field(
        default="",
        description="Describes any potential vulnerabilities directly exposed in this definition, such as "
        "a potential buffer overflow, use-after-free, double free, accessing null pointer, etc., "
        "as identified by an LLM.",
    )
    control_flow: str = Field(
        default="",
        description="Describes what other functions/methods this definition may call. If any vulnerabilities are "
        "associated with those calls, such information should be mentioned here as well.",
    )


class Definition(BaseModel):
    """Extended definition information with additional contextual data.

    This class inherits from PureDefinition (which serves as its fingerprint)
    and adds comprehensive information about the definition's context and behavior.
    The design is extensible, allowing future additions of more definition-related
    data without breaking the core identification mechanism provided by PureDefinition.

    A definition is where a function or method is declared/implemented,
    including the location and any function calls made within its body.
    """

    location: CodeLocation
    """The code location where the definition occurs."""

    doc: str | None = Field(default=None)  # todo: this field is not saved under sqlite persistence
    """Optional documentation string for the definition, if available."""

    calls: list[SymbolReference] = Field(default_factory=list)
    """List of function/method calls made within this definition.

    This may include calls inside any wrapped functions, closures, or lambdas inside the definition.
    """

    llm_note: LLMNote | None = Field(
        default=None
    )  # todo: this field is not saved under sqlite persistence
    """Optional note generated by an LLM about this definition."""

    source_code: str | None = Field(
        None,
        description="The source code of the definition. This field is only used when it is returned by a querying api, and is not saved in the index.",
    )

    def to_pure(self) -> PureDefinition:
        """Extract the pure fingerprint of this definition for use as a dictionary key.

        Returns:
            A PureDefinition containing only the location information,
            suitable for hashing and fast lookups.
        """
        return PureDefinition(location=self.location)

    @classmethod
    def from_pure(cls, pure_def: PureDefinition) -> "Definition":
        """Create a Definition instance from a PureDefinition.

        This method allows creating a Definition instance with an empty context
        (no calls) from a PureDefinition, which is useful for initializing
        definitions before additional context is added.

        Args:
            pure_def (PureDefinition): The pure definition to convert.

        Returns:
            Definition: A new Definition instance with the same location as the PureDefinition.
        """
        return cls(location=pure_def.location, calls=[])

    def add_callee(self, callee: SymbolReference) -> "Definition":
        """Add a callee reference to this definition.

        This method allows adding a reference to a function or method that is called
        within this definition. It ensures that the callee is added only if it is not already present.

        Args:
            callee (SymbolReference): The callee reference to add.

        Returns:
            Definition: The updated Definition instance with the new callee(s) added.
        """
        if callee not in self.calls:
            self.calls.append(callee)
        return self

    def set_note(self, note: LLMNote) -> "Definition":
        """Add or update the LLM-generated note for this definition.

        Args:
            note (LLMNote): The LLM-generated note to add or update.

        Returns:
            Definition: The updated Definition instance with the new note.
        """
        self.llm_note = note
        return self

    def merge(self, other: "Definition") -> None:
        """Merge information about the same PureDefinition.

        This method allows merging additional contextual information from another Definition
        into this one, such as additional calls made within the definition.

        Args:
            other (Definition): Another Definition instance with additional context to merge.

        Raises:
            ValueError: If the other definition does not have the same PureDefinition.
        """
        if self.location != other.location:  # equivalent to PureDefinition equality
            raise ValueError("Cannot merge definitions with different PureDefinition locations.")

        # add doc if not already set
        if self.doc is None:
            self.doc = other.doc

        # Merge the calls
        for callee in other.calls:
            self.add_callee(callee)

        # override llm_note with new one if it exists
        # to support updating the note
        if other.llm_note is not None:
            self.llm_note = other.llm_note


class FunctionLikeInfo(BaseModel):
    """Contains comprehensive information about a function or method.

    Aggregates all known information about a function or method, including
    all its definitions (in case of overloads or multiple declarations)
    and all references to it throughout the codebase.
    """

    definitions: list[Definition] = Field(default_factory=list)
    """List of all definition locations for this symbol."""
    references: list[Reference] = Field(default_factory=list)
    """List of all reference locations for this symbol."""


class IndexDataEntry(BaseModel):
    """Represents a single entry in the serialized index data.

    Each entry associates a function or method symbol with its complete
    information including definitions and references.
    """

    symbol: FunctionLike
    """The function or method symbol."""
    info: FunctionLikeInfo
    """Complete information about the symbol."""


class IndexData(BaseModel):
    """Represents the complete index data in a serializable format.

    This is the top-level container for all indexed information about
    functions and methods in a codebase. Used for persistence and
    data exchange between different index implementations.
    """

    type: str
    """String identifier indicating the index type (e.g., "simple_index")."""
    data: list[IndexDataEntry] = Field(default_factory=list)
    """List of all indexed symbol entries."""
    metadata: dict[Any, Any] | None = None
    """Optional metadata about the index, such as the indexer version, creation timestamp, etc."""
