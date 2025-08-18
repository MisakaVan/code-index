"""
Tests for CrossRefIndex.find_full_definition
"""

from pathlib import Path

from code_index.index.impl.cross_ref_index import CrossRefIndex
from code_index.models import (
    CodeLocation,
    Definition,
    Function,
    FunctionLikeInfo,
    Method,
    PureDefinition,
    Reference,
)


def make_loc(fname: str, ln: int) -> CodeLocation:
    return CodeLocation(
        file_path=Path(fname),
        start_lineno=ln,
        start_col=0,
        end_lineno=ln,
        end_col=10,
        start_byte=ln * 10,
        end_byte=ln * 10 + 10,
    )


def test_find_full_definition_basic_found_and_missing():
    index = CrossRefIndex()
    f = Function(name="foo")
    d = Definition(location=make_loc("m.py", 3))
    index.add_definition(f, d)

    # Found
    res = index.find_full_definition(d.to_pure())
    assert res is not None
    symbol, full = res
    assert symbol == f
    assert full == d

    # Missing
    missing = PureDefinition(location=make_loc("x.py", 99))
    assert index.find_full_definition(missing) is None


def test_find_full_definition_multiple_symbols_same_location():
    index = CrossRefIndex()
    f = Function(name="foo")
    m = Method(name="foo", class_name="C")
    d = Definition(location=make_loc("m.py", 10))

    index.add_definition(f, d)
    index.add_definition(m, d)

    res = index.find_full_definition(d.to_pure())
    assert res is not None
    symbol, full = res
    # Either owner is acceptable depending on mapping order
    assert symbol in {f, m}
    assert full == d


def test_find_full_definition_after_update_and_update_from_data_rebuilds_mapping():
    index = CrossRefIndex()
    f = Function(name="foo")
    d1 = Definition(location=make_loc("a.py", 1))
    d2 = Definition(location=make_loc("a.py", 2))
    r1 = Reference(location=make_loc("a.py", 5))

    # Use update with FunctionLikeInfo
    info = FunctionLikeInfo(definitions=[d1, d2], references=[r1])
    index.update({f: info})

    # Both definitions should be resolvable
    assert index.find_full_definition(d1.to_pure()) is not None
    assert index.find_full_definition(d2.to_pure()) is not None

    # Round-trip via as_data / update_from_data
    data = index.as_data()
    new_index = CrossRefIndex()
    new_index.update_from_data(data)
    assert new_index.find_full_definition(d1.to_pure()) is not None
    assert new_index.find_full_definition(d2.to_pure()) is not None


def test_find_full_definition_after_set_and_delete_maintains_mapping():
    index = CrossRefIndex()
    f = Function(name="foo")
    d1 = Definition(location=make_loc("a.py", 1))
    d2 = Definition(location=make_loc("a.py", 2))

    # __setitem__ should register mapping for both definitions
    index[f] = FunctionLikeInfo(definitions=[d1, d2], references=[])
    assert index.find_full_definition(d1.to_pure()) is not None
    assert index.find_full_definition(d2.to_pure()) is not None

    # __delitem__ should remove mapping
    del index[f]
    assert index.find_full_definition(d1.to_pure()) is None
    assert index.find_full_definition(d2.to_pure()) is None


def test_find_full_definition_stale_mapping_rebuild_path():
    # Simulate a stale mapping by mutating internal store directly (not typical usage)
    index = CrossRefIndex()
    f = Function(name="foo")
    d = Definition(location=make_loc("a.py", 1))
    index.add_definition(f, d)

    # Corrupt internal dict to remove the definition but keep mapping
    pure = d.to_pure()
    # Directly drop definition entry
    info = index.data[f]
    info.definitions.pop(pure)

    # The fast path would see symbol but missing definition, triggering rebuild and yielding None
    res = index.find_full_definition(pure)
    assert res is None
