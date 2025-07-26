import sys
from loguru import logger

__all__ = ["logger"]


# configure the logger
logger.remove()  # 移除默认的日志处理器

# stderr handler, with colored output
logger.add(
    sink=sys.stderr,
    level="DEBUG",
    backtrace=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    colorize=True,
)
