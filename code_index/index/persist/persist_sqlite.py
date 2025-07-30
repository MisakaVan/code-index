from pathlib import Path
from pprint import pprint
from typing import List, Type, TypeVar
from enum import StrEnum

from sqlalchemy import (
    create_engine,
    ForeignKey,
    String,
    Integer,
    Table,
    Column,
    UniqueConstraint,
    select,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
    Session,
)

from ...utils.logger import logger
from ...models import (
    FunctionLike,
    Method,
    Function,
    FunctionLikeInfo,
    CodeLocation,
    Reference,
    IndexDataEntry,
    Definition,
    FunctionLikeRef,
)
from ..base import IndexData, PersistStrategy


# --- 1. 定义所有模型的基础类 ---
class Base(DeclarativeBase):
    pass


# --- 2. 定义多对多关系的连接表 (Association Table) ---
# 因为 definition_references 表只包含外键，没有其他额外的数据，
# 所以我们不需要为它创建一个完整的 ORM 模型类。
# 只需要定义一个 Table 对象即可，SQLAlchemy 会用它来管理多对多关系。
definition_references_table = Table(
    "definition_references",
    Base.metadata,
    Column("definition_id", ForeignKey("definitions.id"), primary_key=True),
    Column("reference_id", ForeignKey("references.id"), primary_key=True),
)

# --- 3. 定义核心实体模型 ---


class SymbolType(StrEnum):
    FUNCTION = "FUNCTION"
    METHOD = "METHOD"


class OrmSymbol(Base):
    __tablename__ = "symbols"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    class_name: Mapped[str | None] = mapped_column(String)
    symbol_type: Mapped[SymbolType] = mapped_column(String)

    # 关系：一个 OrmSymbol 可���有多个 OrmDefinition 和 OrmReference
    definitions: Mapped[List["OrmDefinition"]] = relationship(back_populates="symbol")
    references: Mapped[List["OrmReference"]] = relationship(back_populates="symbol")

    __table_args__ = (UniqueConstraint("name", "class_name", name="uq_symbol_name_class"),)

    def __repr__(self) -> str:
        return f"OrmSymbol(id={self.id!r}, name={self.name!r}, class_name={self.class_name!r})"


class OrmCodeLocation(Base):
    __tablename__ = "code_locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_path: Mapped[str] = mapped_column(String)
    start_lineno: Mapped[int] = mapped_column(Integer)
    start_col: Mapped[int] = mapped_column(Integer)
    end_lineno: Mapped[int] = mapped_column(Integer)
    end_col: Mapped[int] = mapped_column(Integer)
    start_byte: Mapped[int] = mapped_column(Integer)
    end_byte: Mapped[int] = mapped_column(Integer)

    # 关系：一个 OrmCodeLocation 可以被多个 OrmDefinition 和 OrmReference 使用
    definitions: Mapped[List["OrmDefinition"]] = relationship(back_populates="location")
    references: Mapped[List["OrmReference"]] = relationship(back_populates="location")

    def __repr__(self) -> str:
        return (
            f"OrmCodeLocation(id={self.id!r}, path={self.file_path!r}, line={self.start_lineno!r})"
        )


class OrmDefinition(Base):
    __tablename__ = "definitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id"))
    location_id: Mapped[int] = mapped_column(ForeignKey("code_locations.id"))

    # 关系：一个 OrmDefinition 属于一个 OrmSymbol 和一个 OrmCodeLocation
    symbol: Mapped["OrmSymbol"] = relationship(back_populates="definitions")
    location: Mapped["OrmCodeLocation"] = relationship(back_populates="definitions")

    # 关系：一个 OrmDefinition (函数体) 内部可以包含多个 OrmReference (调用)
    # 这是一个多对多关系，通过 definition_references_table 连接
    internal_references: Mapped[List["OrmReference"]] = relationship(
        secondary=definition_references_table, back_populates="callers"
    )

    def __repr__(self) -> str:
        return f"OrmDefinition(id={self.id!r}, symbol_id={self.symbol_id!r})"


class OrmReference(Base):
    __tablename__ = "references"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id"))
    location_id: Mapped[int] = mapped_column(ForeignKey("code_locations.id"))

    # 关系：一个 OrmReference 指向一个 OrmSymbol，并发生在一个 OrmCodeLocation
    symbol: Mapped["OrmSymbol"] = relationship(back_populates="references")
    location: Mapped["OrmCodeLocation"] = relationship(back_populates="references")

    # 关系：一个 OrmReference (调用) 可能被包含在多个 OrmDefinition (函数体) 中
    # (例如，在 Python 的嵌套函数中)
    callers: Mapped[List["OrmDefinition"]] = relationship(
        secondary=definition_references_table, back_populates="internal_references"
    )

    def __repr__(self) -> str:
        return f"OrmReference(id={self.id!r}, symbol_id={self.symbol_id!r})"


class OrmMetadata(Base):
    __tablename__ = "metadata"

    index_type: Mapped[str] = mapped_column(primary_key=True)


T = TypeVar("T", bound=Base)


# helper function
def get_or_create(session: Session, model_cls: Type[T], **kwargs) -> tuple[T, bool]:
    """
    获取或创建一个 ORM 实例。

    :param session: SQLAlchemy 会话对象
    :param model_cls: ORM 模型类
    :param kwargs: 用于查询或创建的字段参数
    :return: 返回找到的实例或新创建的实例；如果实例已存在，则返回 (instance, False)；如果新创建，则返回 (instance, True)
    """
    instance = session.execute(select(model_cls).filter_by(**kwargs)).scalar_one_or_none()
    if instance is not None:
        return instance, False
    else:
        instance = model_cls(**kwargs)
        session.add(instance)
        return instance, True


class SqlitePersistStrategy(PersistStrategy):

    def get_engine(self, path: Path | None = None):
        """
        获取 SQLite 数据库引擎。
        如果 path 为 None，则使用内存数据库。
        """
        if path is None:
            return create_engine("sqlite:///:memory:")
        else:
            if path.exists() and path.is_dir():
                path = path / "index.sqlite"
            # 创建父目录而不是文件路径本身
            path.parent.mkdir(parents=True, exist_ok=True)
            return create_engine(f"sqlite:///{str(path.resolve())}")

    @staticmethod
    def _func_like_as_criteria(func_like: FunctionLike) -> dict:
        match func_like:
            case Function(name=name):
                return {"name": name, "class_name": None, "symbol_type": SymbolType.FUNCTION}
            case Method(name=name, class_name=class_name):
                return {"name": name, "class_name": class_name, "symbol_type": SymbolType.METHOD}
        raise ValueError(
            f"Unsupported FunctionLike type: {type(func_like)}. Expected Function or Method."
        )

    @staticmethod
    def _location_as_criteria(location: CodeLocation) -> dict:
        """
        将 CodeLocation 转换为查询条件字典。
        """
        return {
            "file_path": str(location.file_path),
            "start_lineno": location.start_lineno,
            "start_col": location.start_col,
            "end_lineno": location.end_lineno,
            "end_col": location.end_col,
            "start_byte": location.start_byte,
            "end_byte": location.end_byte,
        }

    def _handle_definition_for_symbol(
        self, session: Session, symbol_db: OrmSymbol, definition_dc: Definition
    ):
        # make location
        loc_db, _ = get_or_create(
            session,
            OrmCodeLocation,
            **self._location_as_criteria(definition_dc.location),
        )

        # make definition
        definition_db, _ = get_or_create(
            session,
            OrmDefinition,
            symbol=symbol_db,  # this should add this definition to the symbol's definitions
            location=loc_db,
        )

        # handle what this definition calls
        for func_ref in definition_dc.calls:
            called_symbol_dc: FunctionLike = func_ref.symbol
            called_reference_dc: Reference = func_ref.reference

            # make called symbol
            called_symbol_db, _ = get_or_create(
                session,
                OrmSymbol,
                **self._func_like_as_criteria(called_symbol_dc),
            )
            # make called location
            called_location_db, _ = get_or_create(
                session,
                OrmCodeLocation,
                **self._location_as_criteria(called_reference_dc.location),
            )
            # make called reference
            called_reference_db, _ = get_or_create(
                session,
                OrmReference,
                symbol=called_symbol_db,
                location=called_location_db,
            )

            # add the reference to the definition-reference relationship
            if called_reference_db not in definition_db.internal_references:
                definition_db.internal_references.append(called_reference_db)

    def _handle_reference_for_symbol(
        self, session: Session, symbol_db: OrmSymbol, reference_dc: Reference
    ):
        # make location
        loc_db, _ = get_or_create(
            session,
            OrmCodeLocation,
            **self._location_as_criteria(reference_dc.location),
        )

        # make reference
        reference_db, _ = get_or_create(
            session,
            OrmReference,
            symbol=symbol_db,  # this should add this reference to the symbol's references
            location=loc_db,
        )

    def _handle_entry(self, session: Session, entry: IndexDataEntry):
        symbol_dc: FunctionLike = entry.symbol
        info_dc: FunctionLikeInfo = entry.info

        # make symbol
        symbol_criteria = self._func_like_as_criteria(symbol_dc)
        symbol_db, _ = get_or_create(session, OrmSymbol, **symbol_criteria)

        # handle info of this symbol
        for definition_dc in info_dc.definitions:
            self._handle_definition_for_symbol(session, symbol_db, definition_dc)

        # handle references of this symbol
        for reference_dc in info_dc.references:
            self._handle_reference_for_symbol(session, symbol_db, reference_dc)

    def _save(self, data: IndexData, session: Session):
        index_type = data.type
        index_data = data.data

        # save metadata
        metadata = OrmMetadata(index_type=index_type)
        session.add(metadata)

        for entry in index_data:
            self._handle_entry(session, entry)

    def save(self, data: IndexData, path: Path):
        """
        将索引数据保存到 SQLite 数据库。

        :param data: 要保存的索引数据字典
        :param path: 保存数据库文件的路径
        """
        engine = self.get_engine(path)
        logger.debug("Created engine at {}", path)
        Base.metadata.create_all(engine)
        session_maker = sessionmaker(bind=engine)
        session = session_maker()
        try:
            self._save(data, session)
            session.commit()
        except Exception as e:
            session.rollback()
            raise RuntimeError(f"保存索引数据到 SQLite 数据库时出错：{e}")
        finally:
            session.close()

    @staticmethod
    def _make_function_like(symbol_db: OrmSymbol) -> FunctionLike:
        """
        根据 OrmSymbol 创建 FunctionLike 对象。
        """
        if symbol_db.symbol_type == SymbolType.FUNCTION:
            return Function(name=symbol_db.name)
        elif symbol_db.symbol_type == SymbolType.METHOD:
            return Method(name=symbol_db.name, class_name=symbol_db.class_name)
        else:
            raise ValueError(f"Unsupported symbol type: {symbol_db.symbol_type}")

    def _handle_load_reference(self, session: Session, ref_db: OrmReference) -> Reference:
        loc_db = ref_db.location
        location = CodeLocation(
            file_path=Path(loc_db.file_path),
            start_lineno=loc_db.start_lineno,
            start_col=loc_db.start_col,
            end_lineno=loc_db.end_lineno,
            end_col=loc_db.end_col,
            start_byte=loc_db.start_byte,
            end_byte=loc_db.end_byte,
        )
        return Reference(location=location)

    def _handle_load_definition(self, session: Session, def_db: OrmDefinition) -> Definition:
        # get the location for this definition
        loc_db = def_db.location
        location = CodeLocation(
            file_path=Path(loc_db.file_path),
            start_lineno=loc_db.start_lineno,
            start_col=loc_db.start_col,
            end_lineno=loc_db.end_lineno,
            end_col=loc_db.end_col,
            start_byte=loc_db.start_byte,
            end_byte=loc_db.end_byte,
        )
        # handle what this definition calls
        calls: list[FunctionLikeRef] = []
        for ref_db in def_db.internal_references:
            calls.append(
                FunctionLikeRef(
                    symbol=self._make_function_like(ref_db.symbol),
                    reference=self._handle_load_reference(session, ref_db),
                )
            )
        # create the definition object
        return Definition(
            location=location,
            calls=calls,
        )

    def _handle_load_info_for_symbol(
        self, session: Session, symbol_db: OrmSymbol
    ) -> FunctionLikeInfo:
        # get the definitions for this symbol
        definitions = []
        for def_db in symbol_db.definitions:
            definition = self._handle_load_definition(session, def_db)
            definitions.append(definition)

        # get the references for this symbol
        references = []
        for ref_db in symbol_db.references:
            reference = self._handle_load_reference(session, ref_db)
            references.append(reference)

        # create the FunctionLikeInfo object
        return FunctionLikeInfo(
            definitions=definitions,
            references=references,
        )

    def _load(self, session: Session) -> IndexData:
        """
        从 SQLAlchemy 会话中加载索引数据。

        :param session: SQLAlchemy 会话对象
        :return: IndexData 对象
        """
        metadata = session.query(OrmMetadata).one_or_none()
        if metadata is None:
            raise ValueError("数据库中没有找到索引元数据。")

        index_type: str = metadata.index_type  # type: ignore

        symbols = session.query(OrmSymbol).all()
        entries = []
        for symbol in symbols:
            entries.append(
                IndexDataEntry(
                    symbol=self._make_function_like(symbol),
                    info=self._handle_load_info_for_symbol(session, symbol),
                )
            )

        return IndexData(type=index_type, data=entries)

    def load(self, path: Path) -> IndexData:
        """
        从 SQLite 数据库加载索引数据。

        :param path: SQLite 数据库文件的路径
        :return: IndexData 对象
        """
        engine = self.get_engine(path)
        logger.debug("Created engine at {}", path)
        session_maker = sessionmaker(bind=engine)
        session = session_maker()

        try:
            return self._load(session)
        except Exception as e:
            raise RuntimeError(f"从 SQLite 数据库加载索引数据时出错：{e}")
        finally:
            session.close()


def demo_orm():
    # 创建一个内存中的 SQLite 数据库引擎用于演示
    engine = create_engine("sqlite:///:memory:")
    # 根据我们定义的模型，在数据库中创建所有表
    Base.metadata.create_all(engine)
    # 创建一个 Session 类，用于与数据库交互
    session_maker = sessionmaker(bind=engine)
    session = session_maker()
    # --- 创建一些示例数据 ---
    session.add(OrmMetadata(index_type="demo_index"))
    # 1. 创建符号
    main_func_symbol = OrmSymbol(name="main", symbol_type=SymbolType.FUNCTION)
    helper_func_symbol = OrmSymbol(name="helper_func", symbol_type=SymbolType.FUNCTION)
    # 2. 创建位置
    main_loc = OrmCodeLocation(
        file_path="main.c",
        start_lineno=10,
        start_col=1,
        end_lineno=15,
        end_col=1,
        start_byte=11,
        end_byte=45,
    )
    helper_loc = OrmCodeLocation(
        file_path="main.c",
        start_lineno=1,
        start_col=1,
        end_lineno=5,
        end_col=1,
        start_byte=2,
        end_byte=30,
    )
    call_loc = OrmCodeLocation(
        file_path="main.c",
        start_lineno=12,
        start_col=5,
        end_lineno=12,
        end_col=18,
        start_byte=50,
        end_byte=70,
    )
    # 3. 创建定义
    main_def = OrmDefinition(symbol=main_func_symbol, location=main_loc)
    helper_def = OrmDefinition(symbol=helper_func_symbol, location=helper_loc)
    # 4. 创建引用
    helper_ref = OrmReference(symbol=helper_func_symbol, location=call_loc)
    # 5. 建立调用关系：main 函数内部调用了 helper_func
    main_def.internal_references.append(helper_ref)
    # 将所有对象添加到 session 中
    session.add_all([main_func_symbol, helper_func_symbol, main_def, helper_def, helper_ref])
    # 提交事务，将数据写入数据库
    session.commit()
    # --- 查询数据 ---
    print("--- 查询数据库 ---")
    # 查找 main 函数的定义
    retrieved_main_def = (
        session.query(OrmDefinition).filter(OrmDefinition.symbol.has(name="main")).one()
    )
    # 打印 main 函数内部调用的函数名
    print(f"函数 '{retrieved_main_def.symbol.name}' 内部调用了:")
    for ref in retrieved_main_def.internal_references:
        print(f"  - '{ref.symbol.name}' (位于行 {ref.location.start_lineno})")
    session.close()

    # 读取数据
    persist_strategy = SqlitePersistStrategy()
    load_session = session_maker()
    try:
        index_data = persist_strategy._load(load_session)
        print("--- 读取索引数据 ---")
        pprint(index_data)
    except Exception as e:
        print(f"读取索引数据时出错: {e}")
    finally:
        load_session.close()


# --- 4. 示例：如何使用这些模型 ---
if __name__ == "__main__":
    demo_orm()
