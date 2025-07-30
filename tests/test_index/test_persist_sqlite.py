import pytest
import tempfile

from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from code_index.index.persist.persist_sqlite import (
    SqlitePersistStrategy,
    SymbolType,
    OrmSymbol,
    OrmMetadata,
    OrmReference,
    OrmDefinition,
    OrmCodeLocation,
)
from code_index.models import *


# make locations a fixture
@pytest.fixture
def locations() -> list[CodeLocation]:
    return [
        CodeLocation(
            file_path=Path(f"/path/to/file_{i}.py"),
            start_lineno=i,
            start_col=1,
            end_lineno=50 + i,
            end_col=i,
            start_byte=i * 10,
            end_byte=i * 10 + 100,
        )
        for i in range(1, 11)
    ]


@pytest.fixture
def sample_index_data(
    locations: list[CodeLocation],
) -> IndexData:

    # locations = [
    #     CodeLocation(
    #         file_path=Path(f"/path/to/file_{i}.py"),
    #         start_lineno=i,
    #         start_col=1,
    #         end_lineno=50 + i,
    #         end_col=i,
    #         start_byte=i * 10,
    #         end_byte=i * 10 + 100,
    #     )
    #     for i in range(1, 11)
    # ]

    func_1_entry: IndexDataEntry = IndexDataEntry(
        symbol=Function(name="func_1"),
        info=FunctionLikeInfo(
            definitions=[
                Definition(
                    location=locations[0],
                    calls=[],
                )
            ],
            references=[
                Reference(
                    location=locations[1],
                )
            ],
        ),
    )

    func_2_entry: IndexDataEntry = IndexDataEntry(
        symbol=Function(name="func_2"),
        info=FunctionLikeInfo(
            definitions=[
                Definition(
                    location=locations[2],
                    calls=[
                        FunctionLikeRef(
                            symbol=Function(name="func_1"),
                            reference=Reference(
                                location=locations[1],
                            ),
                        )
                    ],
                )
            ],
            references=[
                Reference(
                    location=locations[3],
                )
            ],
        ),
    )

    # func_3 calls func_1 and func_2.
    func_3_entry: IndexDataEntry = IndexDataEntry(
        symbol=Method(name="func_3", class_name="ClassFoo"),
        info=FunctionLikeInfo(
            definitions=[
                Definition(
                    location=locations[4],
                    calls=[
                        FunctionLikeRef(
                            symbol=func_1_entry.symbol,
                            reference=func_1_entry.info.references[0],
                        ),
                        FunctionLikeRef(
                            symbol=func_2_entry.symbol,
                            reference=func_2_entry.info.references[0],
                        ),
                    ],
                )
            ],
            references=[
                Reference(
                    location=locations[5],
                ),
                Reference(
                    location=locations[6],
                ),
            ],
        ),
    )

    # there are 7 different locations
    return IndexData(
        type="test_index",
        data=[func_1_entry, func_2_entry, func_3_entry],
    )


# @pytest.mark.skip("WIP")
class TestSqlitePersistStrategy:
    def test_save_simple_data(self, locations: list[CodeLocation], sample_index_data: IndexData):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "test_index.sqlite"
            strategy = SqlitePersistStrategy()
            strategy.save(sample_index_data, path)

            # Verify that the file was created
            assert path.exists()

            engine = create_engine(f"sqlite:///{str(path.resolve())}")
            session_maker = sessionmaker(bind=engine)
            session = session_maker()

            try:
                assert session.query(OrmSymbol).count() == 3  # func_1, func_2, func_3
                assert session.query(OrmCodeLocation).count() == 7  # 7 different locations appeared
                assert (
                    session.query(OrmDefinition).count() == 3
                )  # func_1, func_2, func_3 each has one definition
                assert (
                    session.query(OrmReference).count() == 4
                )  # func_1 has 1 ref, func_2 has 1 ref, func_3 has 2 refs

                # Verify the index-level metadata
                metadata = session.query(OrmMetadata).one()
                assert metadata.index_type == "test_index"

                # Verify the data for func_1
                func_1_db = session.query(OrmSymbol).filter_by(name="func_1").one()
                assert func_1_db.symbol_type == SymbolType.FUNCTION
                assert func_1_db.definitions.__len__() == 1
                assert func_1_db.references.__len__() == 1
                assert func_1_db.class_name is None

                func_1_def = func_1_db.definitions[0]
                assert func_1_def.location.file_path == str(locations[0].file_path)
                func_1_ref = func_1_db.references[0]
                assert func_1_ref.location.file_path == str(locations[1].file_path)

                # Verify the data for func_2
                func_2_db = session.query(OrmSymbol).filter_by(name="func_2").one()
                assert func_2_db.symbol_type == SymbolType.FUNCTION
                assert func_2_db.definitions.__len__() == 1
                assert func_2_db.class_name is None

                func_2_def: OrmDefinition = func_2_db.definitions[0]  # type: ignore
                assert func_2_def.location.file_path == str(locations[2].file_path)
                assert func_2_def.internal_references.__len__() == 1
                assert func_2_def.internal_references[0].symbol.name == "func_1"
                assert (
                    func_2_def.internal_references[0] == func_1_ref
                )  # should be the same row in the database

                # Verify the data for func_3
                func_3_db = session.query(OrmSymbol).filter_by(name="func_3").one()
                assert func_3_db.symbol_type == SymbolType.METHOD
                assert func_3_db.definitions.__len__() == 1
                assert func_3_db.class_name == "ClassFoo"
                func_3_def: OrmDefinition = func_3_db.definitions[0]  # type: ignore
                assert func_3_def.location.file_path == str(locations[4].file_path)
                assert func_3_def.internal_references.__len__() == 2
                assert func_3_def.internal_references[0].symbol.name == "func_1"
                assert func_3_def.internal_references[1].symbol.name == "func_2"

            finally:
                session.close()

    def test_save_and_load_data(self, sample_index_data: IndexData):
        """测试保存和加载数据的完整流程，验证数据的一致性"""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "test_index.sqlite"
            strategy = SqlitePersistStrategy()
            strategy.save(sample_index_data, path)
            assert path.exists()

            loaded_data = strategy.load(path)
            assert loaded_data.type == sample_index_data.type
            assert len(loaded_data.data) == len(sample_index_data.data)

            # 将数据转换为字典，以便比较（不考虑顺序）
            def entry_to_dict(entry: IndexDataEntry) -> dict:
                """将 IndexDataEntry 转换为字典用于比较"""
                symbol_dict = {
                    "type": type(entry.symbol).__name__,
                    "name": entry.symbol.name,
                }
                if hasattr(entry.symbol, "class_name"):
                    symbol_dict["class_name"] = entry.symbol.class_name

                def location_to_dict(loc: CodeLocation) -> dict:
                    return {
                        "file_path": str(loc.file_path),
                        "start_lineno": loc.start_lineno,
                        "start_col": loc.start_col,
                        "end_lineno": loc.end_lineno,
                        "end_col": loc.end_col,
                        "start_byte": loc.start_byte,
                        "end_byte": loc.end_byte,
                    }

                def reference_to_dict(ref: Reference) -> dict:
                    return {"location": location_to_dict(ref.location)}

                def func_like_ref_to_dict(func_ref: FunctionLikeRef) -> dict:
                    ref_symbol_dict = {
                        "type": type(func_ref.symbol).__name__,
                        "name": func_ref.symbol.name,
                    }
                    if hasattr(func_ref.symbol, "class_name"):
                        ref_symbol_dict["class_name"] = func_ref.symbol.class_name

                    return {
                        "symbol": ref_symbol_dict,
                        "reference": reference_to_dict(func_ref.reference),
                    }

                def definition_to_dict(defn: Definition) -> dict:
                    return {
                        "location": location_to_dict(defn.location),
                        "calls": sorted(
                            [func_like_ref_to_dict(call) for call in defn.calls],
                            key=lambda x: (x["symbol"]["name"], x["symbol"]["type"]),
                        ),
                    }

                return {
                    "symbol": symbol_dict,
                    "info": {
                        "definitions": sorted(
                            [definition_to_dict(defn) for defn in entry.info.definitions],
                            key=lambda x: (
                                x["location"]["file_path"],
                                x["location"]["start_lineno"],
                            ),
                        ),
                        "references": sorted(
                            [reference_to_dict(ref) for ref in entry.info.references],
                            key=lambda x: (
                                x["location"]["file_path"],
                                x["location"]["start_lineno"],
                            ),
                        ),
                    },
                }

            # 转换原始数据和加载数据为字典
            original_entries = sorted(
                [entry_to_dict(entry) for entry in sample_index_data.data],
                key=lambda x: (x["symbol"]["name"], x["symbol"]["type"]),
            )
            loaded_entries = sorted(
                [entry_to_dict(entry) for entry in loaded_data.data],
                key=lambda x: (x["symbol"]["name"], x["symbol"]["type"]),
            )

            # 逐个比较条目
            for i, (original, loaded) in enumerate(zip(original_entries, loaded_entries)):
                assert (
                    original == loaded
                ), f"Entry {i} mismatch:\nOriginal: {original}\nLoaded: {loaded}"
