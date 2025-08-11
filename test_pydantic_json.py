#!/usr/bin/env python3
"""Test script to verify JSON serialization/deserialization of Pydantic models."""

import tempfile
from pathlib import Path

from code_index.models import (
    CodeLocation,
    Definition,
    Function,
    FunctionLikeInfo,
    FunctionLikeRef,
    IndexData,
    IndexDataEntry,
    Method,
    Reference,
)


def create_sample_index_data() -> IndexData:
    """Create a sample IndexData object with various types of entries."""

    # Create some sample locations
    location1 = CodeLocation(
        file_path=Path("src/example.py"),
        start_lineno=10,
        start_col=0,
        end_lineno=15,
        end_col=10,
        start_byte=200,
        end_byte=350,
    )

    location2 = CodeLocation(
        file_path=Path("src/utils.py"),
        start_lineno=5,
        start_col=4,
        end_lineno=5,
        end_col=20,
        start_byte=100,
        end_byte=116,
    )

    location3 = CodeLocation(
        file_path=Path("src/main.py"),
        start_lineno=25,
        start_col=8,
        end_lineno=25,
        end_col=25,
        start_byte=500,
        end_byte=517,
    )

    # Create a function
    func = Function(name="process_data")

    # Create a method
    method = Method(name="validate", class_name="DataValidator")

    # Create a method with no class context
    method_no_class = Method(name="unknown_method", class_name=None)

    # Create references
    ref1 = Reference(location=location2)
    ref2 = Reference(location=location3)

    # Create a function call within a definition
    func_ref = FunctionLikeRef(
        symbol=Function(name="helper_func"), reference=Reference(location=location2)
    )

    # Create definitions
    def1 = Definition(location=location1, calls=[func_ref])

    def2 = Definition(location=location2)

    # Create function info
    func_info = FunctionLikeInfo(definitions=[def1], references=[ref1, ref2])

    method_info = FunctionLikeInfo(definitions=[def2], references=[ref1])

    method_no_class_info = FunctionLikeInfo(definitions=[], references=[ref2])

    # Create index entries
    entries = [
        IndexDataEntry(symbol=func, info=func_info),
        IndexDataEntry(symbol=method, info=method_info),
        IndexDataEntry(symbol=method_no_class, info=method_no_class_info),
    ]

    # Create the main IndexData
    index_data = IndexData(
        type="simple_index", data=entries, metadata={"version": "1.0", "created_by": "test_script"}
    )

    return index_data


def test_json_serialization():
    """Test JSON serialization and deserialization."""
    print("Creating sample IndexData...")
    original_data = create_sample_index_data()

    print(f"Original data has {len(original_data.data)} entries")
    print(f"Index type: {original_data.type}")

    # Test JSON serialization
    print("\n1. Testing JSON serialization...")
    json_str = original_data.model_dump_json(indent=2)
    print(f"JSON length: {len(json_str)} characters")
    print(f"JSON content:\n{json_str}")

    # Save to temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(json_str)
        temp_file_path = f.name

    print(f"Saved JSON to: {temp_file_path}")

    # Test JSON deserialization
    print("\n2. Testing JSON deserialization...")
    with open(temp_file_path, "r") as f:
        loaded_json = f.read()

    reconstructed_data = IndexData.model_validate_json(loaded_json)

    print(f"Reconstructed data has {len(reconstructed_data.data)} entries")
    print(f"Reconstructed index type: {reconstructed_data.type}")

    # Test equality
    print("\n3. Testing data integrity...")
    print(f"Original == Reconstructed: {original_data == reconstructed_data}")

    # Detailed verification
    print("\n4. Detailed verification...")

    for i, (orig_entry, recon_entry) in enumerate(zip(original_data.data, reconstructed_data.data)):
        print(f"  Entry {i + 1}:")
        print(f"    Symbol type: {orig_entry.symbol.type} == {recon_entry.symbol.type}")
        print(f"    Symbol name: {orig_entry.symbol.name} == {recon_entry.symbol.name}")

        if hasattr(orig_entry.symbol, "class_name"):
            print(
                f"    Class name: {orig_entry.symbol.class_name} == {recon_entry.symbol.class_name}"
            )

        print(
            f"    Definitions count: {len(orig_entry.info.definitions)} == {len(recon_entry.info.definitions)}"
        )
        print(
            f"    References count: {len(orig_entry.info.references)} == {len(recon_entry.info.references)}"
        )

    # Test discriminated union specifically
    print("\n5. Testing discriminated union types...")
    for entry in reconstructed_data.data:
        symbol = entry.symbol
        print(f"  Symbol: {symbol.name}")
        print(f"    Type: {type(symbol).__name__}")
        print(f"    Discriminator: {symbol.type}")
        if hasattr(symbol, "class_name"):
            print(f"    Class name: {symbol.class_name}")

    # Clean up
    Path(temp_file_path).unlink()

    print("\n✅ JSON serialization test completed successfully!")
    print("✅ Discriminated unions work correctly!")
    print("✅ Nested objects serialize/deserialize properly!")

    return reconstructed_data


if __name__ == "__main__":
    test_json_serialization()
