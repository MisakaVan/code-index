import os
import sys

from dotenv import load_dotenv
from loguru import logger

__all__ = ["logger"]


def setup_logger():
    load_dotenv(override=False)

    log_level = os.getenv("CODE_INDEX_LOG_LEVEL", "INFO").upper()

    # configure the logger
    logger.remove()  # 移除默认的日志处理器

    # stderr handler, with colored output
    logger.add(
        sink=sys.stderr,
        level=log_level,
        backtrace=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )


setup_logger()

logger.debug("Logger debug message")
logger.info("Logger info message")
