import argparse
from pathlib import Path
from pprint import pprint

from code_index.language_processor import language_processor_factory

# 使用相对导入，从同一个包中导入 CodeIndexer
from .indexer import CodeIndexer


def main():
    """
    命令行接口的主函数。
    """
    parser = argparse.ArgumentParser(
        description="CodeIndex: 一个用于索引源代码中函数定义和引用的命令行工具。"
    )

    parser.add_argument("repo_path", type=Path, help="需要被索引的代码仓库或目录的路径。")

    parser.add_argument(
        "-l",
        "--language",
        type=str,
        default="python",
        choices=["python", "c", "cpp"],
        help="指定要索引的编程语言。默认为 'python'。",
    )

    parser.add_argument("-f", "--find", type=str, help="索引完成后，要查找的特定函数名。")

    parser.add_argument(
        "-d",
        "--dump",
        action="store_true",
        help="将索引结果导出为 JSON 文件。默认导出到 repo_path/index.json。",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="指定导出索引结果的 JSON 文件路径。如果未指定，则默认为 repo_path/index.json。",
    )

    args = parser.parse_args()

    if args.output is None:
        # 如果没有指定输出路径，则使用 repo_path/index.json
        args.output = args.repo_path / "index.json"
    else:
        args.dump = True  # 如果指定了输出路径，则默认启用导出功能

    # make sure the output path is a file
    if args.output.is_dir():
        print(f"错误：提供的输出路径 '{args.output}' 是一个目录，请指定一个文件路径。")
        return

    # 检查仓库路径是否存在
    if not args.repo_path.exists() or not args.repo_path.is_dir():
        print(f"错误：提供的路径 '{args.repo_path}' 不是一个有效的目录。")
        return

    try:
        processor = language_processor_factory(args.language)
        assert processor is not None, f"未找到适用于 '{args.language}' 的语言处理器。"
        indexer = CodeIndexer(processor)
    except AssertionError as e:
        print(f"错误：初始化索引器失败。{e}")
        return

    # 2. 对指定的项目路径进行索引
    indexer.index_project(args.repo_path)

    print("\n--- 索引结果 ---")
    pprint(indexer.index)  # 打印索引结果

    # 3. 如果用户指定了要查找的函数，则执行查询并打印结果
    if args.find:
        func_to_find = args.find
        print(f"\n--- 查询 '{func_to_find}' 的结果 ---")

        definitions = indexer.find_definitions(func_to_find)
        if definitions:
            print(f"\n✅ 找到 {len(definitions)} 个定义:")
            pprint(definitions)
        else:
            print(f"\n❌ 未找到 '{func_to_find}' 的定义。")

        references = indexer.find_references(func_to_find)
        if references:
            print(f"\n✅ 找到 {len(references)} 个引用:")
            pprint(references)
        else:
            print(f"\n❌ 未找到 '{func_to_find}' 的引用。")

    # 4. 如果用户指定了导出索引，则将索引数据导出为 JSON 文件
    if args.dump:
        try:
            indexer.dump_index(args.output)
        except Exception as e:
            print(f"错误：导出索引失败。{e}")
            return

        print(f"\n索引数据已导出到 {args.output}")


if __name__ == "__main__":
    main()
