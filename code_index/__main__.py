import argparse
import time
from pathlib import Path

from .index.persist.persist_json import SingleJsonFilePersistStrategy
from .index.persist.persist_sqlite import SqlitePersistStrategy
from .indexer import CodeIndexer
from .language_processor import language_processor_factory
from .utils.logger import logger


def main():
    """Command-line interface for the code-index tool.

    This function provides a command-line interface for indexing source code
    repositories and exporting the results in various formats. It supports
    multiple programming languages and persistence strategies.

    For detailed usage information, run:
        uv run -m code_index --help

    Note:
        This function is designed to be called from the command line via the
        entry point defined in pyproject.toml.
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

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="指定导出索引结果的文件或目录路径（相对于要解析的项目根目录）。如果未指定，则默认为 repo_path 下的 [index.json/index.sqlite]。",
    )

    # select persist strategy
    parser.add_argument(
        "--dump-type",
        "--dt",
        type=str,
        default="json",
        choices=["json", "sqlite", "none"],
        help="指定导出索引数据的格式。默认为 'json'。",
    )

    args = parser.parse_args()

    # 检查 repo_path 是否为存在的目录
    if not args.repo_path.is_dir():
        logger.error(f"提供的路径 '{args.repo_path}' 不是一个有效的目录。")
        exit(1)

    # 持久化策略
    persist_strategy = None
    if args.dump_type == "json":
        persist_strategy = SingleJsonFilePersistStrategy()
        default_filename = "index.json"
    elif args.dump_type == "sqlite":
        persist_strategy = SqlitePersistStrategy()
        default_filename = "index.sqlite"
    elif args.dump_type == "none":
        pass
    else:
        logger.error(f"不支持的持久化策略 '{args.dump_type}'。")
        exit(1)

    if persist_strategy:
        if args.output is None:
            # 如果没有指定输出路径，则使用 repo_path/index.json
            args.output = args.repo_path

        # make sure the output path is a file
        if args.output.is_dir():
            # fallback to default file name based on dump type
            logger.info(
                f"输出路径 '{args.output}' 是一个目录，将使用默认文件名 '{default_filename}'。"
            )
            args.output = args.output / default_filename

        logger.info(f"索引结果将导出到: {args.output}")

    start_time = time.time()
    try:
        processor = language_processor_factory(args.language)
        assert processor is not None, f"未找到适用于 '{args.language}' 的语言处理器。"
        indexer = CodeIndexer(processor)
    except AssertionError as e:
        logger.error(f"初始化索引器失败。{e}")
        exit(1)

    # 2. 对指定的项目路径进行索引
    indexer.index_project(args.repo_path)

    logger.info("--- 索引结果 ---")
    logger.info(f"索引完成。共索引了 {len(indexer.index)} 个符号。")
    logger.info(f"索引耗时: {time.time() - start_time:.2f} 秒")

    if persist_strategy:
        try:
            indexer.index.persist_to(args.output, persist_strategy)
        except Exception as e:
            logger.error(f"导出索引失败。{e}")
            exit(1)

        logger.success(f"索引数据已导出到 {args.output}")


if __name__ == "__main__":
    main()
