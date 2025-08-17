"""
Tests for SimpleIndex.find_full_definition
"""

from pathlib import Path

from code_index.index.impl.simple_index import SimpleIndex
from code_index.models import CodeLocation, Definition, Function, Method, PureDefinition


def make_loc(fname: str, start: int) -> CodeLocation:
    return CodeLocation(
        file_path=Path(fname),
        start_lineno=start,
        start_col=0,
        end_lineno=start,
        end_col=10,
        start_byte=start * 10,
        end_byte=start * 10 + 10,
    )


def test_find_full_definition_found_and_not_found():
    index = SimpleIndex()

    func = Function(name="f")
    loc = make_loc("a.py", 1)
    d = Definition(location=loc)
    index.add_definition(func, d)

    # Found
    pure = d.to_pure()
    found = index.find_full_definition(pure)
    assert found is not None
    symbol, full = found
    assert symbol == func
    assert full == d

    # Not found
    missing = PureDefinition(location=make_loc("b.py", 99))
    assert index.find_full_definition(missing) is None


def test_find_full_definition_multiple_symbols_same_location():
    """When multiple symbols share the same definition location, any one is acceptable."""
    index = SimpleIndex()

    func = Function(name="f")
    method = Method(name="f", class_name="C")
    loc = make_loc("a.py", 10)
    d = Definition(location=loc)

    # Add to two symbols with the same Definition instance/location
    index.add_definition(func, d)
    index.add_definition(method, d)

    result = index.find_full_definition(d.to_pure())
    assert result is not None
    symbol, full = result
    # May return either owner depending on insertion/scan order
    assert symbol in {func, method}
    assert full == d
