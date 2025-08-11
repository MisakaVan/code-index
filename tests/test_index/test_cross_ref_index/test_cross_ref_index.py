"""Tests for CrossRefIndex and related classes."""

from pathlib import Path

import pytest

from code_index.index.code_query import (
    FilterOption,
    QueryByKey,
    QueryByName,
    QueryByNameRegex,
)
from code_index.index.impl.cross_ref_index import (
    CrossRefIndex,
    DefinitionDict,
    ReferenceDict,
)
from code_index.models import (
    CodeLocation,
    Definition,
    Function,
    FunctionLikeInfo,
    Method,
    PureDefinition,
    PureReference,
    Reference,
    SymbolDefinition,
    SymbolReference,
)


@pytest.fixture
def sample_location():
    """Sample code location for testing."""
    return CodeLocation(
        file_path=Path("test.py"),
        start_lineno=10,
        start_col=5,
        end_lineno=10,
        end_col=15,
        start_byte=100,
        end_byte=110,
    )


@pytest.fixture
def sample_location2():
    """Another sample code location for testing."""
    return CodeLocation(
        file_path=Path("test.py"),
        start_lineno=20,
        start_col=8,
        end_lineno=20,
        end_col=18,
        start_byte=200,
        end_byte=210,
    )


@pytest.fixture
def sample_function():
    """Sample function for testing."""
    return Function(name="test_func")


@pytest.fixture
def sample_method():
    """Sample method for testing."""
    return Method(name="test_method", class_name="TestClass")


def make_position(
    file_path, start_lineno, start_col, end_lineno, end_col, start_byte, end_byte
) -> CodeLocation:
    """Helper function to create a CodeLocation."""
    return CodeLocation(
        file_path=Path(file_path),
        start_lineno=start_lineno,
        start_col=start_col,
        end_lineno=end_lineno,
        end_col=end_col,
        start_byte=start_byte,
        end_byte=end_byte,
    )


class TestReferenceDict:
    """Tests for ReferenceDict class."""

    def test_invariant_enforcement(self, sample_location, sample_location2):
        """Test that the invariant key == value.to_pure() is enforced."""
        ref_dict = ReferenceDict()

        pure_ref = PureReference(location=sample_location)
        reference = Reference(location=sample_location)

        # This should work - key matches value.to_pure()
        ref_dict[pure_ref] = reference
        assert ref_dict[pure_ref] == reference

        # This should fail - key doesn't match value.to_pure()
        wrong_pure_ref = PureReference(location=sample_location2)
        with pytest.raises(ValueError, match="Key .* does not match value.to_pure()"):
            ref_dict[wrong_pure_ref] = reference

    def test_auto_creation_on_missing_key(self, sample_location):
        """Test that missing keys automatically create new Reference objects."""
        ref_dict = ReferenceDict()
        pure_ref = PureReference(location=sample_location)

        # Accessing non-existent key should create new Reference
        reference = ref_dict[pure_ref]
        assert isinstance(reference, Reference)
        assert reference.location == sample_location
        assert reference.to_pure() == pure_ref
        assert pure_ref in ref_dict

    def test_merge_or_insert_new_entry(self, sample_location, sample_function):
        """Test merge_or_insert with a new entry."""
        ref_dict = ReferenceDict()

        symbol_def = SymbolDefinition(
            symbol=sample_function, definition=PureDefinition(location=sample_location)
        )
        reference = Reference(location=sample_location, called_by=[symbol_def])

        ref_dict.merge_or_insert(reference)

        pure_ref = reference.to_pure()
        assert pure_ref in ref_dict
        assert ref_dict[pure_ref].called_by == [symbol_def]

    def test_merge_or_insert_existing_entry(
        self, sample_location, sample_function, sample_location2
    ):
        """Test merge_or_insert with an existing entry."""
        ref_dict = ReferenceDict()

        # Create first reference with one caller
        symbol_def1 = SymbolDefinition(
            symbol=sample_function, definition=PureDefinition(location=sample_location)
        )
        reference1 = Reference(location=sample_location, called_by=[symbol_def1])
        ref_dict.merge_or_insert(reference1)

        # Create second reference with another caller
        symbol_def2 = SymbolDefinition(
            symbol=Function(name="another_func"),
            definition=PureDefinition(location=sample_location2),
        )
        reference2 = Reference(location=sample_location, called_by=[symbol_def2])
        ref_dict.merge_or_insert(reference2)

        # Should have merged the called_by lists
        pure_ref = reference1.to_pure()
        merged_ref = ref_dict[pure_ref]
        assert len(merged_ref.called_by) == 2
        assert symbol_def1 in merged_ref.called_by
        assert symbol_def2 in merged_ref.called_by


class TestDefinitionDict:
    """Tests for DefinitionDict class."""

    def test_invariant_enforcement(self, sample_location, sample_location2):
        """Test that the invariant key == value.to_pure() is enforced."""
        def_dict = DefinitionDict()

        pure_def = PureDefinition(location=sample_location)
        definition = Definition(location=sample_location)

        # This should work - key matches value.to_pure()
        def_dict[pure_def] = definition
        assert def_dict[pure_def] == definition

        # This should fail - key doesn't match value.to_pure()
        wrong_pure_def = PureDefinition(location=sample_location2)
        with pytest.raises(ValueError, match="Key .* does not match value.to_pure()"):
            def_dict[wrong_pure_def] = definition

    def test_auto_creation_on_missing_key(self, sample_location):
        """Test that missing keys automatically create new Definition objects."""
        def_dict = DefinitionDict()
        pure_def = PureDefinition(location=sample_location)

        # Accessing non-existent key should create new Definition
        definition = def_dict[pure_def]
        assert isinstance(definition, Definition)
        assert definition.location == sample_location
        assert definition.to_pure() == pure_def
        assert pure_def in def_dict

    def test_merge_or_insert_new_entry(self, sample_location, sample_function):
        """Test merge_or_insert with a new entry."""
        def_dict = DefinitionDict()

        symbol_ref = SymbolReference(
            symbol=sample_function, reference=PureReference(location=sample_location)
        )
        definition = Definition(location=sample_location, calls=[symbol_ref])

        def_dict.merge_or_insert(definition)

        pure_def = definition.to_pure()
        assert pure_def in def_dict
        assert def_dict[pure_def].calls == [symbol_ref]

    def test_merge_or_insert_existing_entry(
        self, sample_location, sample_function, sample_location2
    ):
        """Test merge_or_insert with an existing entry."""
        def_dict = DefinitionDict()

        # Create first definition with one call
        symbol_ref1 = SymbolReference(
            symbol=sample_function, reference=PureReference(location=sample_location)
        )
        definition1 = Definition(location=sample_location, calls=[symbol_ref1])
        def_dict.merge_or_insert(definition1)

        # Create second definition with another call
        symbol_ref2 = SymbolReference(
            symbol=Function(name="another_func"), reference=PureReference(location=sample_location2)
        )
        definition2 = Definition(location=sample_location, calls=[symbol_ref2])
        def_dict.merge_or_insert(definition2)

        # Should have merged the calls lists
        pure_def = definition1.to_pure()
        merged_def = def_dict[pure_def]
        assert len(merged_def.calls) == 2
        assert symbol_ref1 in merged_def.calls
        assert symbol_ref2 in merged_def.calls


class TestCrossRefIndexInfo:
    """Tests for CrossRefIndex.Info class."""

    def test_to_function_like_info(self, sample_location, sample_function):
        """Test conversion to FunctionLikeInfo."""
        info = CrossRefIndex.Info()

        # Add a definition and reference
        definition = Definition(location=sample_location)
        reference = Reference(location=sample_location)

        pure_def = definition.to_pure()
        pure_ref = reference.to_pure()

        info.definitions[pure_def] = definition
        info.references[pure_ref] = reference

        func_like_info = info.to_function_like_info()

        assert isinstance(func_like_info, FunctionLikeInfo)
        assert len(func_like_info.definitions) == 1
        assert len(func_like_info.references) == 1
        assert definition in func_like_info.definitions
        assert reference in func_like_info.references

    def test_from_function_like_info(self, sample_location):
        """Test creation from FunctionLikeInfo."""
        definition = Definition(location=sample_location)
        reference = Reference(location=sample_location)

        func_like_info = FunctionLikeInfo(definitions=[definition], references=[reference])

        info = CrossRefIndex.Info.from_function_like_info(func_like_info)

        assert len(info.definitions) == 1
        assert len(info.references) == 1
        assert definition.to_pure() in info.definitions
        assert reference.to_pure() in info.references

    def test_update_from_info(self, sample_location, sample_location2, sample_function):
        """Test updating from another Info object."""
        info1 = CrossRefIndex.Info()
        info2 = CrossRefIndex.Info()

        # Add different items to each info
        def1 = Definition(location=sample_location)
        ref1 = Reference(location=sample_location)

        def2 = Definition(location=sample_location2)
        ref2 = Reference(location=sample_location2)

        info1.definitions[def1.to_pure()] = def1
        info1.references[ref1.to_pure()] = ref1

        info2.definitions[def2.to_pure()] = def2
        info2.references[ref2.to_pure()] = ref2

        # Update info1 with info2
        info1.update_from(info2)

        assert len(info1.definitions) == 2
        assert len(info1.references) == 2
        assert def1.to_pure() in info1.definitions
        assert def2.to_pure() in info1.definitions
        assert ref1.to_pure() in info1.references
        assert ref2.to_pure() in info1.references

    def test_update_from_function_like_info(self, sample_location, sample_location2):
        """Test updating from FunctionLikeInfo."""
        info = CrossRefIndex.Info()

        # Add initial items
        def1 = Definition(location=sample_location)
        info.definitions[def1.to_pure()] = def1

        # Create FunctionLikeInfo with new items
        def2 = Definition(location=sample_location2)
        ref2 = Reference(location=sample_location2)

        func_like_info = FunctionLikeInfo(definitions=[def2], references=[ref2])

        # Update with FunctionLikeInfo
        info.update_from(func_like_info)

        assert len(info.definitions) == 2
        assert len(info.references) == 1
        assert def1.to_pure() in info.definitions
        assert def2.to_pure() in info.definitions
        assert ref2.to_pure() in info.references


class TestCrossRefIndex:
    """Tests for CrossRefIndex class."""

    def test_initialization(self):
        """Test CrossRefIndex initialization."""
        index = CrossRefIndex()
        assert len(index) == 0
        assert isinstance(index.data, dict)

    def test_add_definition_simple(self, sample_function, sample_location):
        """Test adding a simple definition without calls."""
        index = CrossRefIndex()
        definition = Definition(location=sample_location)

        index.add_definition(sample_function, definition)

        assert sample_function in index
        info = index.get_info(sample_function)
        assert len(info.definitions) == 1
        assert definition in info.definitions

    def test_add_definition_with_cross_reference(self, sample_location, sample_location2):
        """Test adding a definition with cross-reference to another function."""
        index = CrossRefIndex()

        caller_func = Function(name="caller")
        called_func = Function(name="called")

        # Create a definition that calls another function
        symbol_ref = SymbolReference(
            symbol=called_func, reference=PureReference(location=sample_location2)
        )
        caller_definition = Definition(location=sample_location, calls=[symbol_ref])

        # Add the definition
        index.add_definition(caller_func, caller_definition)

        # Check that the definition was added
        caller_info = index.get_info(caller_func)
        assert len(caller_info.definitions) == 1
        assert caller_definition in caller_info.definitions

        # Check that cross-reference was established
        called_info = index.get_info(called_func)
        assert len(called_info.references) == 1

        # The called function should have this reference in its references
        called_ref = list(called_info.references)[0]
        assert called_ref.location == sample_location2

        # The reference should show that it's called by the caller function
        assert len(called_ref.called_by) == 1
        symbol_def = called_ref.called_by[0]
        assert symbol_def.symbol == caller_func
        assert symbol_def.definition == caller_definition.to_pure()

    def test_add_reference_simple(self, sample_function, sample_location):
        """Test adding a simple reference without callers."""
        index = CrossRefIndex()
        reference = Reference(location=sample_location)

        index.add_reference(sample_function, reference)

        assert sample_function in index
        info = index.get_info(sample_function)
        assert len(info.references) == 1
        assert reference in info.references

    def test_add_reference_with_cross_reference(self, sample_location, sample_location2):
        """Test adding a reference with cross-reference to caller function."""
        index = CrossRefIndex()

        caller_func = Function(name="caller")
        called_func = Function(name="called")

        # Create a reference that is called by another function
        symbol_def = SymbolDefinition(
            symbol=caller_func, definition=PureDefinition(location=sample_location)
        )
        called_reference = Reference(location=sample_location2, called_by=[symbol_def])

        # Add the reference
        index.add_reference(called_func, called_reference)

        # Check that the reference was added
        called_info = index.get_info(called_func)
        assert len(called_info.references) == 1
        assert called_reference in called_info.references

        # Check that cross-reference was established
        caller_info = index.get_info(caller_func)
        assert len(caller_info.definitions) == 1

        # The caller function should have this call in its definitions
        caller_def = list(caller_info.definitions)[0]
        assert caller_def.location == sample_location

        # The definition should show that it calls the called function
        assert len(caller_def.calls) == 1
        symbol_ref = caller_def.calls[0]
        assert symbol_ref.symbol == called_func
        assert symbol_ref.reference == called_reference.to_pure()

    def test_bidirectional_cross_reference(self, sample_location, sample_location2):
        """Test that adding both definition and reference creates proper bidirectional links."""
        index = CrossRefIndex()

        func_a = Function(name="func_a")
        func_b = Function(name="func_b")

        # func_a calls func_b
        symbol_ref = SymbolReference(
            symbol=func_b, reference=PureReference(location=sample_location2)
        )
        definition_a = Definition(location=sample_location, calls=[symbol_ref])

        # func_b is called by func_a
        symbol_def = SymbolDefinition(
            symbol=func_a, definition=PureDefinition(location=sample_location)
        )
        reference_b = Reference(location=sample_location2, called_by=[symbol_def])

        # Add both
        index.add_definition(func_a, definition_a)
        index.add_reference(func_b, reference_b)

        # Verify bidirectional relationship
        info_a = index.get_info(func_a)
        info_b = index.get_info(func_b)

        # func_a should have definition that calls func_b
        assert len(info_a.definitions) == 1
        def_a = list(info_a.definitions)[0]
        assert len(def_a.calls) == 1
        assert def_a.calls[0].symbol == func_b

        # func_b should have reference that is called by func_a
        assert len(info_b.references) == 1
        ref_b = list(info_b.references)[0]
        assert len(ref_b.called_by) == 1
        assert ref_b.called_by[0].symbol == func_a

    def test_query_by_key(self, sample_function, sample_location):
        """Test querying by specific function key."""
        index = CrossRefIndex()
        definition = Definition(location=sample_location)
        index.add_definition(sample_function, definition)

        query = QueryByKey(func_like=sample_function)
        results = index.handle_query(query)

        assert len(results) == 1
        assert results[0].func_like == sample_function
        assert len(results[0].info.definitions) == 1

    def test_query_by_name_function(self, sample_location):
        """Test querying by function name."""
        index = CrossRefIndex()
        func1 = Function(name="test_func")
        func2 = Function(name="other_func")
        method1 = Method(name="test_func", class_name="TestClass")

        index.add_definition(func1, Definition(location=sample_location))
        index.add_definition(func2, Definition(location=sample_location))
        index.add_definition(method1, Definition(location=sample_location))

        # Query for functions named "test_func"
        query = QueryByName(name="test_func", type_filter=FilterOption.FUNCTION)
        results = index.handle_query(query)

        assert len(results) == 1
        assert results[0].func_like == func1

    def test_query_by_name_method(self, sample_location):
        """Test querying by method name."""
        index = CrossRefIndex()
        func1 = Function(name="test_func")
        method1 = Method(name="test_func", class_name="TestClass")

        index.add_definition(func1, Definition(location=sample_location))
        index.add_definition(method1, Definition(location=sample_location))

        # Query for methods named "test_func"
        query = QueryByName(name="test_func", type_filter=FilterOption.METHOD)
        results = index.handle_query(query)

        assert len(results) == 1
        assert results[0].func_like == method1

    def test_query_by_name_all(self, sample_location):
        """Test querying by name with no type filter."""
        index = CrossRefIndex()
        func1 = Function(name="test_func")
        method1 = Method(name="test_func", class_name="TestClass")

        index.add_definition(func1, Definition(location=sample_location))
        index.add_definition(method1, Definition(location=sample_location))

        # Query for all items named "test_func"
        query = QueryByName(name="test_func", type_filter=FilterOption.ALL)
        results = index.handle_query(query)

        assert len(results) == 2
        func_likes = {result.func_like for result in results}
        assert func1 in func_likes
        assert method1 in func_likes

    def test_query_by_name_regex(self, sample_location):
        """Test querying by regex pattern."""
        index = CrossRefIndex()
        func1 = Function(name="test_func")
        func2 = Function(name="test_method")
        func3 = Function(name="other_func")

        index.add_definition(func1, Definition(location=sample_location))
        index.add_definition(func2, Definition(location=sample_location))
        index.add_definition(func3, Definition(location=sample_location))

        # Query for functions matching "test_.*"
        query = QueryByNameRegex(name_regex="test_.*", type_filter=FilterOption.ALL)
        results = index.handle_query(query)

        assert len(results) == 2
        func_likes = {result.func_like for result in results}
        assert func1 in func_likes
        assert func2 in func_likes
        assert func3 not in func_likes

    def test_query_invalid_regex(self):
        """Test that invalid regex patterns raise ValueError."""
        index = CrossRefIndex()

        query = QueryByNameRegex(name_regex="[invalid", type_filter=FilterOption.ALL)
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            index.handle_query(query)

    def test_serialization_roundtrip(self, sample_function, sample_location):
        """Test that index can be serialized and deserialized."""
        index = CrossRefIndex()
        definition = Definition(location=sample_location)
        index.add_definition(sample_function, definition)

        # Serialize to IndexData
        data = index.as_data()
        assert data.type == "cross_ref_index"
        assert len(data.data) == 1

        # Create new index and deserialize
        new_index = CrossRefIndex()
        new_index.update_from_data(data)

        # Verify the data was restored
        assert sample_function in new_index
        info = new_index.get_info(sample_function)
        assert len(info.definitions) == 1
        restored_def = list(info.definitions)[0]
        assert restored_def.location == sample_location

    def test_update_method(self, sample_function, sample_location, sample_location2):
        """Test the update method with mapping."""
        index = CrossRefIndex()

        # Create FunctionLikeInfo with multiple definitions and references
        def1 = Definition(location=sample_location)
        def2 = Definition(location=sample_location2)
        ref1 = Reference(location=sample_location)

        info = FunctionLikeInfo(definitions=[def1, def2], references=[ref1])

        mapping = {sample_function: info}
        index.update(mapping)

        # Verify the data was added
        stored_info = index.get_info(sample_function)
        assert len(stored_info.definitions) == 2
        assert len(stored_info.references) == 1

    def test_merge_on_duplicate_addition(self, sample_function, sample_location):
        """Test that adding the same definition/reference multiple times merges properly."""
        index = CrossRefIndex()

        # Add the same definition twice
        definition = Definition(location=sample_location)
        index.add_definition(sample_function, definition)
        index.add_definition(sample_function, definition)

        # Should still only have one definition (but potentially merged content)
        info = index.get_info(sample_function)
        assert len(info.definitions) == 1

    def test_complex_cross_reference_scenario(self):
        """Test a complex scenario with multiple functions calling each other."""
        index = CrossRefIndex()

        # Create locations
        loc_main = make_position(Path("main.py"), 1, 0, 1, 10, 0, 10)
        loc_func_a = make_position(Path("main.py"), 5, 0, 5, 10, 50, 60)
        loc_func_b = make_position(Path("main.py"), 10, 0, 10, 10, 100, 110)
        loc_call_a = make_position(Path("main.py"), 2, 4, 2, 10, 20, 26)
        loc_call_b1 = make_position(Path("main.py"), 3, 4, 3, 10, 30, 36)
        loc_call_b2 = make_position(Path("main.py"), 6, 4, 6, 10, 70, 76)

        # Create functions
        main_func = Function(name="main")
        func_a = Function(name="func_a")
        func_b = Function(name="func_b")

        # main() calls func_a() and func_b()
        main_def = Definition(
            location=loc_main,
            calls=[
                SymbolReference(symbol=func_a, reference=PureReference(location=loc_call_a)),
                SymbolReference(symbol=func_b, reference=PureReference(location=loc_call_b1)),
            ],
        )

        # func_a() calls func_b()
        func_a_def = Definition(
            location=loc_func_a,
            calls=[
                SymbolReference(symbol=func_b, reference=PureReference(location=loc_call_b2)),
            ],
        )

        # func_b() doesn't call anything
        func_b_def = Definition(location=loc_func_b, calls=[])

        # Add all definitions
        index.add_definition(main_func, main_def)
        index.add_definition(func_a, func_a_def)
        index.add_definition(func_b, func_b_def)

        # Verify cross-references
        main_info = index.get_info(main_func)
        func_a_info = index.get_info(func_a)
        func_b_info = index.get_info(func_b)

        # main should have 1 definition with 2 calls
        assert len(main_info.definitions) == 1
        assert len(list(main_info.definitions)[0].calls) == 2

        # func_a should have 1 definition with 1 call, and 1 reference (called by main)
        assert len(func_a_info.definitions) == 1
        assert len(list(func_a_info.definitions)[0].calls) == 1
        assert len(func_a_info.references) == 1
        func_a_ref = list(func_a_info.references)[0]
        assert len(func_a_ref.called_by) == 1
        assert func_a_ref.called_by[0].symbol == main_func

        # func_b should have 1 definition with 0 calls, and 2 references (called by main and func_a)
        assert len(func_b_info.definitions) == 1
        assert len(list(func_b_info.definitions)[0].calls) == 0
        assert len(func_b_info.references) == 2

        # Check that func_b has the right callers
        func_b_refs = list(func_b_info.references)
        callers = set()
        for ref in func_b_refs:
            for caller in ref.called_by:
                callers.add(caller.symbol)

        assert main_func in callers
        assert func_a in callers

    def test_str_and_repr(self, sample_function, sample_location):
        """Test string representations of the index."""
        index = CrossRefIndex()

        # Test empty index
        repr_str = repr(index)
        assert "CrossRefIndex" in repr_str
        assert "items=0" in repr_str
        assert "total_definitions=0" in repr_str
        assert "total_references=0" in repr_str

        # Add some data
        definition = Definition(location=sample_location)
        index.add_definition(sample_function, definition)

        # Test with data
        repr_str = repr(index)
        assert "items=1" in repr_str
        assert "total_definitions=1" in repr_str
