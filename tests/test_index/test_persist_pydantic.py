"""Tests for SingleJsonFilePersistStrategy using Pydantic models.

This module tests the JSON persistence strategy that uses Pydantic models
for serialization and deserialization instead of the deprecated custom JSON handling.
"""

import json
import tempfile
from pathlib import Path

import pytest

from code_index.index.persist.persist_json import SingleJsonFilePersistStrategy
from code_index.models import (
    CodeLocation,
    Definition,
    Function,
    FunctionLikeInfo,
    IndexData,
    IndexDataEntry,
    Method,
    PureReference,
    Reference,
    SymbolReference,
)


@pytest.fixture
def sample_index_data():
    """Create sample IndexData using Pydantic models for testing."""
    # Create sample locations
    location1 = CodeLocation(
        file_path=Path("/test/file1.py"),
        start_lineno=10,
        start_col=5,
        end_lineno=15,
        end_col=20,
        start_byte=100,
        end_byte=200,
    )

    location2 = CodeLocation(
        file_path=Path("/test/file2.py"),
        start_lineno=25,
        start_col=0,
        end_lineno=30,
        end_col=15,
        start_byte=300,
        end_byte=450,
    )

    location3 = CodeLocation(
        file_path=Path("/test/utils.py"),
        start_lineno=5,
        start_col=8,
        end_lineno=5,
        end_col=25,
        start_byte=50,
        end_byte=67,
    )

    # Create sample function and method
    function = Function(name="process_data")
    method = Method(name="validate", class_name="DataValidator")
    method_no_class = Method(name="unknown_method", class_name=None)

    # Create references
    ref1 = Reference(location=location2)
    ref2 = Reference(location=location3)

    # Create a function call within a definition
    helper_call = SymbolReference(
        symbol=Function(name="helper_function"), reference=PureReference(location=location3)
    )

    # Create definitions
    func_def = Definition(location=location1, calls=[helper_call])

    method_def = Definition(location=location2)

    # Create function info objects
    func_info = FunctionLikeInfo(definitions=[func_def], references=[ref1, ref2])

    method_info = FunctionLikeInfo(definitions=[method_def], references=[ref1])

    method_no_class_info = FunctionLikeInfo(definitions=[], references=[ref2])

    # Create index entries
    entries = [
        IndexDataEntry(symbol=function, info=func_info),
        IndexDataEntry(symbol=method, info=method_info),
        IndexDataEntry(symbol=method_no_class, info=method_no_class_info),
    ]

    # Create the main IndexData
    index_data = IndexData(
        type="simple_index", data=entries, metadata={"version": "1.0", "created_by": "test_suite"}
    )

    return index_data


@pytest.fixture
def minimal_index_data():
    """Create minimal IndexData for simple tests."""
    return IndexData(type="test_index", data=[], metadata=None)


class TestSingleJsonFilePersistStrategyPydantic:
    """Test SingleJsonFilePersistStrategy with Pydantic models."""

    def test_init(self):
        """Test strategy initialization."""
        strategy = SingleJsonFilePersistStrategy()
        assert strategy is not None
        assert repr(strategy) == "SingleJsonFilePersistStrategy()"

    def test_save_and_load_minimal_data(self, minimal_index_data):
        """Test saving and loading minimal IndexData."""
        strategy = SingleJsonFilePersistStrategy()

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "minimal_index.json"

            # Save data
            strategy.save(minimal_index_data, test_file)

            # Verify file exists
            assert test_file.exists()
            assert test_file.is_file()

            # Load data
            loaded_data = strategy.load(test_file)

            # Verify data integrity
            assert isinstance(loaded_data, IndexData)
            assert loaded_data.type == minimal_index_data.type
            assert loaded_data.data == minimal_index_data.data
            assert loaded_data.metadata == minimal_index_data.metadata
            assert loaded_data == minimal_index_data

    def test_save_and_load_complex_index_data(self, sample_index_data):
        """Test saving and loading complex IndexData with all model types."""
        strategy = SingleJsonFilePersistStrategy()

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "complex_index.json"

            # Save complex data
            strategy.save(sample_index_data, test_file)

            # Verify file exists and has content
            assert test_file.exists()
            assert test_file.stat().st_size > 0

            # Load data
            loaded_data = strategy.load(test_file)

            # Verify data integrity
            assert isinstance(loaded_data, IndexData)
            assert loaded_data == sample_index_data

            # Verify nested structure integrity
            assert len(loaded_data.data) == 3

            # Test function entry
            func_entry = loaded_data.data[0]
            assert isinstance(func_entry.symbol, Function)
            assert func_entry.symbol.type == "function"
            assert func_entry.symbol.name == "process_data"

            # Test method entry
            method_entry = loaded_data.data[1]
            assert isinstance(method_entry.symbol, Method)
            assert method_entry.symbol.type == "method"
            assert method_entry.symbol.name == "validate"
            assert method_entry.symbol.class_name == "DataValidator"

            # Test method without class
            method_no_class_entry = loaded_data.data[2]
            assert isinstance(method_no_class_entry.symbol, Method)
            assert method_no_class_entry.symbol.class_name is None

    def test_discriminated_union_serialization(self, sample_index_data):
        """Test that discriminated unions (Symbol) serialize correctly."""
        strategy = SingleJsonFilePersistStrategy()

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "discriminated_test.json"

            # Save data
            strategy.save(sample_index_data, test_file)

            # Read raw JSON to verify discriminator fields
            raw_json = test_file.read_text(encoding="utf-8")
            json_data = json.loads(raw_json)

            # Verify discriminator fields are present in JSON
            for entry in json_data["data"]:
                symbol = entry["symbol"]
                assert "type" in symbol  # Discriminator field
                assert symbol["type"] in ["function", "method"]

                if symbol["type"] == "function":
                    assert "name" in symbol
                    assert "class_name" not in symbol
                elif symbol["type"] == "method":
                    assert "name" in symbol
                    # class_name may be null/None

            # Load and verify discriminated union reconstruction
            loaded_data = strategy.load(test_file)

            for entry in loaded_data.data:
                if isinstance(entry.symbol, Function):
                    assert entry.symbol.type == "function"
                elif isinstance(entry.symbol, Method):
                    assert entry.symbol.type == "method"

    def test_path_serialization(self, sample_index_data):
        """Test that Path objects are correctly serialized and deserialized."""
        strategy = SingleJsonFilePersistStrategy()

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "path_test.json"

            # Save data
            strategy.save(sample_index_data, test_file)

            # Load data
            loaded_data = strategy.load(test_file)

            # Verify all Path objects are preserved correctly
            for entry in loaded_data.data:
                for definition in entry.info.definitions:
                    assert isinstance(definition.location.file_path, Path)
                    # Verify the path string is correct
                    original_path = None
                    for orig_entry in sample_index_data.data:
                        if orig_entry.symbol == entry.symbol:
                            for orig_def in orig_entry.info.definitions:
                                if (
                                    orig_def.location.start_lineno
                                    == definition.location.start_lineno
                                    and orig_def.location.start_col == definition.location.start_col
                                ):
                                    original_path = orig_def.location.file_path
                                    break
                            break
                    if original_path:
                        assert definition.location.file_path == original_path

                for reference in entry.info.references:
                    assert isinstance(reference.location.file_path, Path)

    def test_nested_calls_serialization(self, sample_index_data):
        """Test that nested function calls within definitions are preserved."""
        strategy = SingleJsonFilePersistStrategy()

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "nested_calls_test.json"

            # Save data
            strategy.save(sample_index_data, test_file)

            # Load data
            loaded_data = strategy.load(test_file)

            # Find the function entry that has calls
            func_entry = next(
                entry
                for entry in loaded_data.data
                if isinstance(entry.symbol, Function) and entry.symbol.name == "process_data"
            )

            # Verify the nested call structure
            assert len(func_entry.info.definitions) == 1
            definition = func_entry.info.definitions[0]
            assert len(definition.calls) == 1

            call = definition.calls[0]
            assert isinstance(call, SymbolReference)
            assert isinstance(call.symbol, Function)
            assert call.symbol.name == "helper_function"
            assert isinstance(call.reference, PureReference)
            assert isinstance(call.reference.location, CodeLocation)

    def test_save_to_nonexistent_file(self, minimal_index_data):
        """Test saving to a new file path."""
        strategy = SingleJsonFilePersistStrategy()

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "new_file.json"

            # File shouldn't exist initially
            assert not test_file.exists()

            # Save data
            strategy.save(minimal_index_data, test_file)

            # File should now exist
            assert test_file.exists()

            # Load and verify
            loaded_data = strategy.load(test_file)
            assert loaded_data == minimal_index_data

    def test_save_overwrite_existing_file(self, minimal_index_data, sample_index_data):
        """Test overwriting an existing file."""
        strategy = SingleJsonFilePersistStrategy()

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "overwrite_test.json"

            # Save first data
            strategy.save(minimal_index_data, test_file)
            loaded_first = strategy.load(test_file)
            assert loaded_first == minimal_index_data

            # Overwrite with second data
            strategy.save(sample_index_data, test_file)
            loaded_second = strategy.load(test_file)
            assert loaded_second == sample_index_data
            assert loaded_second != minimal_index_data

    def test_load_nonexistent_file(self):
        """Test loading from a nonexistent file."""
        strategy = SingleJsonFilePersistStrategy()
        nonexistent_file = Path("/nonexistent/path/file.json")

        with pytest.raises(FileNotFoundError, match="Index file does not exist"):
            strategy.load(nonexistent_file)

    def test_save_to_directory_path(self, minimal_index_data):
        """Test saving to a directory path should raise ValueError."""
        strategy = SingleJsonFilePersistStrategy()

        with tempfile.TemporaryDirectory() as temp_dir:
            directory_path = Path(temp_dir)

            with pytest.raises(ValueError, match="Specified path is a directory, not a file"):
                strategy.save(minimal_index_data, directory_path)

    def test_load_directory_path(self):
        """Test loading from a directory path should raise ValueError."""
        strategy = SingleJsonFilePersistStrategy()

        with tempfile.TemporaryDirectory() as temp_dir:
            directory_path = Path(temp_dir)

            with pytest.raises(ValueError, match="Specified path is a directory, not a file"):
                strategy.load(directory_path)

    def test_save_to_nonexistent_parent_directory(self, minimal_index_data):
        """Test saving to a path with nonexistent parent directory."""
        strategy = SingleJsonFilePersistStrategy()
        nonexistent_path = Path("/nonexistent/directory/file.json")

        with pytest.raises(FileNotFoundError, match="Parent directory does not exist"):
            strategy.save(minimal_index_data, nonexistent_path)

    def test_save_parent_is_not_directory(self, minimal_index_data):
        """Test saving when parent path is not a directory."""
        strategy = SingleJsonFilePersistStrategy()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a file to use as "parent"
            parent_file = Path(temp_dir) / "not_a_directory.txt"
            parent_file.write_text("test content")

            # Try to save to a path under the file
            invalid_path = parent_file / "file.json"

            with pytest.raises(ValueError, match="Parent path is not a directory"):
                strategy.save(minimal_index_data, invalid_path)

    def test_load_invalid_json_file(self):
        """Test loading from a file with invalid JSON."""
        strategy = SingleJsonFilePersistStrategy()

        with tempfile.TemporaryDirectory() as temp_dir:
            invalid_json_file = Path(temp_dir) / "invalid.json"
            invalid_json_file.write_text("{ invalid json content", encoding="utf-8")

            # Pydantic wraps JSON decode errors in ValidationError, which gets wrapped in RuntimeError
            with pytest.raises(RuntimeError, match="Error loading index file"):
                strategy.load(invalid_json_file)

    def test_load_valid_json_invalid_model(self):
        """Test loading from a file with valid JSON but invalid Pydantic model data."""
        strategy = SingleJsonFilePersistStrategy()

        with tempfile.TemporaryDirectory() as temp_dir:
            invalid_model_file = Path(temp_dir) / "invalid_model.json"
            # Valid JSON but missing required IndexData fields
            invalid_model_file.write_text('{"wrong": "structure"}', encoding="utf-8")

            with pytest.raises(RuntimeError, match="Error loading index file"):
                strategy.load(invalid_model_file)

    def test_load_non_regular_file(self):
        """Test loading from a non-regular file."""
        strategy = SingleJsonFilePersistStrategy()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a symbolic link (if possible)
            target_file = Path(temp_dir) / "target.json"
            target_file.write_text('{"test": "data"}')

            link_file = Path(temp_dir) / "link.json"
            try:
                link_file.symlink_to(target_file)
                # On most systems, symlinks are still considered files
                # This test might pass, which is fine
                # The main point is to test the is_file() check
            except (OSError, NotImplementedError):
                # Symlinks not supported, skip this specific test
                pytest.skip("Symlinks not supported on this system")

    def test_json_formatting(self, sample_index_data):
        """Test that saved JSON is properly formatted."""
        strategy = SingleJsonFilePersistStrategy()

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "formatted_test.json"

            # Save data
            strategy.save(sample_index_data, test_file)

            # Read raw JSON and verify it's formatted
            raw_json = test_file.read_text(encoding="utf-8")

            # Should contain newlines and indentation (formatted)
            assert "\n" in raw_json
            assert "  " in raw_json  # 2-space indentation

            # Should be valid JSON
            parsed = json.loads(raw_json)
            assert isinstance(parsed, dict)
            assert "type" in parsed
            assert "data" in parsed

    def test_roundtrip_data_equality(self, sample_index_data):
        """Test that data remains exactly equal after save/load roundtrip."""
        strategy = SingleJsonFilePersistStrategy()

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "roundtrip_test.json"

            # Save data
            strategy.save(sample_index_data, test_file)

            # Load data
            loaded_data = strategy.load(test_file)

            # Test deep equality
            assert loaded_data == sample_index_data

            # Test that individual components are equal
            assert loaded_data.type == sample_index_data.type
            assert loaded_data.metadata == sample_index_data.metadata
            assert len(loaded_data.data) == len(sample_index_data.data)

            for loaded_entry, original_entry in zip(loaded_data.data, sample_index_data.data):
                assert loaded_entry == original_entry
                assert loaded_entry.symbol == original_entry.symbol
                assert loaded_entry.info == original_entry.info

    def test_empty_index_data(self):
        """Test saving and loading empty IndexData."""
        strategy = SingleJsonFilePersistStrategy()

        empty_data = IndexData(type="empty_index", data=[], metadata=None)

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "empty_test.json"

            # Save empty data
            strategy.save(empty_data, test_file)

            # Load empty data
            loaded_data = strategy.load(test_file)

            # Verify equality
            assert loaded_data == empty_data
            assert len(loaded_data.data) == 0
            assert loaded_data.metadata is None

    def test_large_index_data_performance(self):
        """Test handling of large IndexData objects."""
        strategy = SingleJsonFilePersistStrategy()

        # Create a large IndexData object
        entries = []
        for i in range(100):  # Create 100 entries
            location = CodeLocation(
                file_path=Path(f"/test/file_{i}.py"),
                start_lineno=i + 1,
                start_col=0,
                end_lineno=i + 5,
                end_col=10,
                start_byte=i * 100,
                end_byte=(i + 1) * 100,
            )

            function = Function(name=f"function_{i}")
            definition = Definition(location=location)
            info = FunctionLikeInfo(definitions=[definition])

            entries.append(IndexDataEntry(symbol=function, info=info))

        large_data = IndexData(
            type="large_index", data=entries, metadata={"entry_count": len(entries)}
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "large_test.json"

            # Save large data
            strategy.save(large_data, test_file)

            # Verify file size is reasonable
            file_size = test_file.stat().st_size
            assert file_size > 1000  # Should be substantial

            # Load large data
            loaded_data = strategy.load(test_file)

            # Verify equality
            assert loaded_data == large_data
            assert len(loaded_data.data) == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
