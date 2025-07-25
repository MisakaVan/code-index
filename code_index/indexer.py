import os
import json
from pathlib import Path
from pprint import pprint
from typing import Dict, List, Optional
from collections import defaultdict

from tree_sitter import Language, Parser, Node, QueryCursor, Tree

from .models import (
    CodeLocation,
    Definition,
    Reference,
    FunctionLikeInfo,
    FunctionLike,
    Function,
    Method,
)
from .language_processor import LanguageProcessor, language_processor_factory, QueryContext
from .utils.custom_json import dump_index_to_json


class CodeIndexer:
    """
    一个使用 tree-sitter 解析源代码并建立索引的类。
    它可以找到函数定义及其所有引用。
    """

    def __init__(self, processor: LanguageProcessor, store_relative_paths: bool = True):
        """
        初始化索引器。

        Args:
            processor: LanguageProcessor: 用于解析源代码的语言处理器实例。
            store_relative_paths: bool: 是否存储相对于project_root的路径，默认为 True。否则，索引将使用绝对路径。
        """
        print("Initializing CodeIndexer...")

        self.processor = processor

        self.store_relative_paths = store_relative_paths

        # 用于存储索引数据的主数据结构
        self.index: Dict[str, FunctionLikeInfo] = defaultdict(lambda: FunctionLikeInfo())

    def _get_node_text(self, node: Node, source_bytes: bytes) -> str:
        """从源代码字节中提取节点的文本。"""
        return source_bytes[node.start_byte : node.end_byte].decode("utf8", errors="ignore")

    def _process_definitions(
        self,
        tree: Tree,
        source_bytes: bytes,
        file_path: Path,
        processor: Optional[LanguageProcessor] = None,
    ):
        """处理文件中的所有函数定义。"""
        if processor is None:
            processor = self.processor
        context = QueryContext(file_path=file_path, source_bytes=source_bytes)
        for node in processor.get_definition_nodes(tree):
            result = processor.handle_definition(node, context)

            match result:
                case (Function() as func, Definition() as def_):
                    self.index[func.name].definition.append(def_)
                case (Method() as method, Definition() as def_):
                    self.index[method.name].definition.append(def_)
                case None:
                    pass

    def _process_references(
        self,
        tree: Tree,
        source_bytes: bytes,
        file_path: Path,
        processor: Optional[LanguageProcessor] = None,
    ):
        """处理文件中的所有函数引用。"""
        if processor is None:
            processor: LanguageProcessor = self.processor
        context = QueryContext(file_path=file_path, source_bytes=source_bytes)
        for node in processor.get_reference_nodes(tree):
            result = processor.handle_reference(node, context)

            match result:
                case (Function() as func, Reference() as ref):
                    self.index[func.name].references.append(ref)
                case (Method() as method, Reference() as ref):
                    self.index[method.name].references.append(ref)
                case None:
                    pass

    def index_file(
        self, file_path: Path, project_path: Path, processor: Optional[LanguageProcessor] = None
    ):
        """
        解析并索引单个文件。
        即使文件扩展名不在支持的列表中，也会尝试解析。
        """
        if not file_path.is_file():
            print(f"Skipping non-file path: {file_path}")
            return
        if not file_path.suffix in self.processor.extensions:
            print(
                f"warning: Unsupported file extension {file_path.suffix} for file {file_path}. Trying to parse anyway."
            )

        if processor is None:
            processor = self.processor

        parser = processor.parser
        lang_name = processor.name
        try:
            source_bytes = file_path.read_bytes()
            print(f"Indexing file: {file_path} as {lang_name}")
        except IOError as e:
            print(f"Error reading file {file_path}: {e}")
            return

        tree = parser.parse(source_bytes)

        if self.store_relative_paths:
            file_path = file_path.relative_to(project_path)

        self._process_definitions(tree, source_bytes, file_path, self.processor)
        self._process_references(tree, source_bytes, file_path, self.processor)

    def index_project(self, project_path: Path):
        """

        递归地索引一个项目目录下的所有支持的文件。
        """
        print(f"\nStarting to index project at: {project_path}")
        for file_path in project_path.rglob("*"):
            if not file_path.is_file():
                continue
            if not file_path.suffix in self.processor.extensions:
                continue
            self.index_file(file_path, project_path, self.processor)
        print("Project indexing complete.")

    def find_definitions(self, name: str) -> List[Definition]:
        """按名称查找函数的定义。"""
        if name not in self.index:
            return []
        return self.index[name].definition

    def find_references(self, name: str) -> List[Reference]:
        """按名称查找函数的所有引用。"""
        if name not in self.index:
            return []
        return self.index[name].references

    def dump_index(self, output_path: Path):
        """
        将索引数据以 JSON 格式写入文件。
        """
        dump_index_to_json(self.index, output_path)


# --- 如何使用这个类的示例 ---
if __name__ == "__main__":
    from .config import PROJECT_ROOT

    indexer = CodeIndexer(language_processor_factory("c"))

    project_to_index = PROJECT_ROOT / "example" / "c"
    if not os.path.exists(project_to_index):
        print(f"示例目录 '{project_to_index}' 不存在，请创建一个或修改路径。")
    else:
        indexer.index_project(project_to_index)

        print("\n--- 查询结果示例 ---")

        func_to_find = "SomeFunction"

        definition = indexer.find_definitions(func_to_find)
        if definition:
            print(f"\n✅ Definition of '{func_to_find}':")
            pprint(definition)
        else:
            print(f"\n❌ No definition found for '{func_to_find}'.")

        references = indexer.find_references(func_to_find)
        if references:
            print(f"\n✅ Found {len(references)} references to '{func_to_find}':")
            pprint(references)
        else:
            print(f"\n❌ No references found for '{func_to_find}'.")

        pprint(indexer.index)

        output_file = project_to_index / "index.json"
        dump_index_to_json(indexer.index, output_file)
