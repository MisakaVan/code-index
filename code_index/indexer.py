import os
from pathlib import Path
from pprint import pprint
from typing import Dict, List, Optional

from tree_sitter import Language, Parser, Node, Query, QueryCursor, Tree
from tree_sitter_language_pack import get_language

# 从我们的数据模型模块中导入 dataclasses
# 假设 models.py 与 indexer.py 在同一个目录下
from .models import CodeLocation, FunctionDefinition, FunctionReference


class CodeIndexer:
    """
    一个使用 tree-sitter 解析源代码并建立索引的类。
    它可以找到函数定义及其所有引用。
    """

    def __init__(self, languages: List[str] = ['python', 'c', 'cpp']):
        """
        初始化索引器。

        Args:
            languages: 一个包含要支持的语言名称的列表。
                       例如: ['python', 'javascript', 'go']
        """
        print("Initializing CodeIndexer...")
        self.parsers: Dict[str, Parser] = {}
        self.language_map: Dict[str, Language] = {}

        # 为每种支持的语言创建一个解析器
        for lang_name in languages:
            try:
                language = get_language(lang_name)
                parser = Parser(language=language)
                self.parsers[lang_name] = parser
                self.language_map[lang_name] = language
                print(f"✅ Language '{lang_name}' loaded successfully.")
            except Exception as e:
                print(f"⚠️ Could not load language '{lang_name}': {e}")

        # 用于存储索引数据的主数据结构
        # 结构: { "function_name": {"definition": FunctionDefinition, "references": [FunctionReference, ...]} }
        self.index: Dict[str, Dict] = {}

        # 定义 tree-sitter 查询语句
        self._setup_queries()

    def _setup_queries(self):
        """为支持的语言编译 tree-sitter 查询。"""
        self.queries: Dict[str, Dict[str, Language.Query]] = {}

        # Python 的查询语句
        if 'python' in self.language_map:
            self.queries['python'] = {
                "definitions": Query(self.language_map['python'], """
                    (function_definition
                        name: (identifier) @function.name) @function.definition
                """),
                "references": Query(self.language_map['python'], """
                    (call
                        function: [(identifier) @function.call
                                   (attribute attribute: (identifier) @method.call)])
                """)
            }

        # C 和 C++ 的查询语句 (C++ 查询可以更复杂，但这里用一个通用的)
        c_like_def_query = """
            (function_definition
                declarator: (function_declarator
                    declarator: (identifier) @function.name
                )
            ) @function.definition
        """
        c_like_ref_query = """
            (call_expression
                function: (identifier) @function.call
            )
        """
        if 'c' in self.language_map:
            self.queries['c'] = {
                # "definitions": self.language_map['c'].query(c_like_def_query),
                "definitions": Query(self.language_map['c'], c_like_def_query),
                "references": Query(self.language_map['c'], c_like_ref_query)
            }
        if 'cpp' in self.language_map:
            self.queries['cpp'] = {
                "definitions": Query(self.language_map['cpp'], c_like_def_query),
                "references": Query(self.language_map['cpp'], c_like_ref_query)
            }
        # 你可以在这里为其他语言添加查询...

    def _get_node_text(self, node: Node, source_bytes: bytes) -> str:
        """从源代码字节中提取节点的文本。"""
        return source_bytes[node.start_byte:node.end_byte].decode('utf8', errors='ignore')

    def _process_definitions(self, tree: Tree, source_bytes: bytes, file_path: Path, lang_name: str):
        """处理文件中的所有函数定义。"""
        lang_queries = self.queries.get(lang_name, {})
        def_query = lang_queries.get("definitions")
        if not def_query: return

        query_cursor = QueryCursor(query=def_query)
        captures = query_cursor.captures(tree.root_node)

        pprint(captures)  # 调试输出，查看捕获的节点

        definition_nodes = captures.get('function.definition', [])
        name_nodes = captures.get('function.name', [])

        # 遍历所有找到的定义节点
        for def_node in definition_nodes:
            # 在所有名称节点中，找到那个被当前定义节点包含的子节点
            child_name_node = next(
                (n for n in name_nodes if n.start_byte >= def_node.start_byte and n.end_byte <= def_node.end_byte),
                None
            )

            if child_name_node:
                func_name = self._get_node_text(child_name_node, source_bytes)
                if func_name not in self.index:
                    self.index[func_name] = {"definition": None, "references": []}

                location = CodeLocation(
                    file_path=file_path,
                    start_lineno=def_node.start_point[0] + 1,
                    start_col=def_node.start_point[1],
                    end_lineno=def_node.end_point[0] + 1,
                    end_col=def_node.end_point[1]
                )
                definition = FunctionDefinition(
                    name=func_name,
                    location=location
                )
                # 这仍然会覆盖重载的函数，但现在能正确配对
                self.index[func_name]["definition"] = definition

    def _process_references(self, tree: Tree, source_bytes: bytes, file_path: Path, lang_name: str):
        """处理文件中的所有函数引用。"""
        lang_queries = self.queries.get(lang_name, {})
        ref_query = lang_queries.get("references")
        if not ref_query: return

        query_cursor = QueryCursor(query=ref_query)
        captures = query_cursor.captures(tree.root_node)

        pprint(captures)  # 调试输出，查看捕获的节点

        call_nodes = captures.get('function.call', [])

        for node in call_nodes:
            ref_name = self._get_node_text(node, source_bytes)
            if ref_name not in self.index:
                self.index[ref_name] = {"definition": None, "references": []}

            location = CodeLocation(
                file_path=file_path,
                start_lineno=node.start_point[0] + 1,
                start_col=node.start_point[1],
                end_lineno=node.end_point[0] + 1,
                end_col=node.end_point[1]
            )
            reference = FunctionReference(
                name=ref_name,
                location=location
            )
            self.index[ref_name]["references"].append(reference)

    def index_file(self, file_path: Path):
        """
        解析并索引单个文件。
        它会根据文件扩展名自动选择合适的解析器。
        """
        file_extension_map = {
            '.py': 'python',
            '.c': 'c', '.h': 'c',
            '.cpp': 'cpp', '.hpp': 'cpp',
        }

        lang_name = file_extension_map.get(file_path.suffix)
        if not lang_name or lang_name not in self.parsers:
            return

        parser = self.parsers[lang_name]
        try:
            source_bytes = file_path.read_bytes()
            print(f"Indexing file: {file_path} as {lang_name}")
        except IOError as e:
            print(f"Error reading file {file_path}: {e}")
            return

        tree = parser.parse(source_bytes)

        self._process_definitions(tree, source_bytes, file_path, lang_name)
        self._process_references(tree, source_bytes, file_path, lang_name)

    def index_project(self, project_path: str):
        """

        递归地索引一个项目目录下的所有支持的文件。
        """
        print(f"\nStarting to index project at: {project_path}")
        root_path = Path(project_path)
        for file_path in root_path.rglob('*'):
            if file_path.is_file():
                self.index_file(file_path)
        print("Project indexing complete.")

    def find_definition(self, name: str) -> Optional[FunctionDefinition]:
        """按名称查找函数的定义。"""
        return self.index.get(name, {}).get("definition")

    def find_references(self, name: str) -> List[FunctionReference]:
        """按名称查找函数的所有引用。"""
        return self.index.get(name, {}).get("references", [])


# --- 如何使用这个类的示例 ---
if __name__ == '__main__':
    from .config import PROJECT_ROOT
    # 创建一个索引器实例，它将自动加载 python, c, cpp 语言
    indexer = CodeIndexer()

    # 指定要索引的项目路径 (例如，当前目录 '.')
    # 为了演示，我们假设有一个名为 'sample_project' 的目录
    project_to_index = PROJECT_ROOT / "example" / "python"
    if not os.path.exists(project_to_index):
        print(f"示例目录 '{project_to_index}' 不存在，请创建一个或修改路径。")
    else:
        indexer.index_project(project_to_index)

        print("\n--- 查询结果示例 ---")

        # 示例查询: 查找 'index_file' 这个函数
        func_to_find = "func1"

        definition = indexer.find_definition(func_to_find)
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

