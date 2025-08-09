import tempfile
from pathlib import Path

import pytest
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
from code_index.utils.test import assert_index_data_equal


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
        for i in range(1, 51)
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
                        SymbolReference(
                            symbol=Function(name="func_1"),
                            reference=PureReference(
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
                        SymbolReference(
                            symbol=func_1_entry.symbol,
                            reference=func_1_entry.info.references[0],
                        ),
                        SymbolReference(
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


@pytest.fixture
def sample_index_integration_data(
    locations: list[CodeLocation],
) -> IndexData:
    """
    Generate a sample index data via a integrated approach.
    Uses a real SimpleIndex instance to create the data.
    """
    from code_index.index.impl.simple_index import SimpleIndex

    index = SimpleIndex()

    # insert 10 symbols, each with 2 references
    for i in range(1, 11):
        func = Function(name=f"func_{i}")
        index.add_reference(
            func,
            Reference(
                location=locations[i],  # 1 through 10
            ),
        )
        index.add_reference(
            func,
            Reference(
                location=locations[i + 10],  # 11 through 20
            ),
        )

        # each function references all previous functions via definitions
        definition_calls = []
        for j in range(1, i):
            prev_func = Function(name=f"func_{j}")
            definition_calls.append(
                SymbolReference(
                    symbol=prev_func,
                    reference=PureReference(location=locations[j]),  # 1 through 10
                )
            )
        index.add_definition(
            func,
            Definition(
                location=locations[i + 20],  # 21 through 30
                calls=definition_calls,
            ),
        )

    return index.as_data()


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

            # 保存数据
            strategy.save(sample_index_data, path)
            assert path.exists()

            # 加载数据
            loaded_data = strategy.load(path)

            # 使用工具函数进行深度比较，不考虑列表顺序
            assert_index_data_equal(
                loaded_data, sample_index_data, "Loaded data does not match original data"
            )

    def test_save_integration_data(self, sample_index_integration_data: IndexData):
        """测试保存集成数据的完整流程，验证数据的一致性"""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "test_index_integration.sqlite"
            strategy = SqlitePersistStrategy()

            # 保存数据
            strategy.save(sample_index_integration_data, path)
            assert path.exists()

            # 加载数据
            loaded_data = strategy.load(path)

            # 使用工具函数进行深度比较，不考虑列表顺序
            assert_index_data_equal(
                loaded_data,
                sample_index_integration_data,
                "Loaded integration data does not match original data",
            )
