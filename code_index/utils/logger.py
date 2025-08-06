"""Logging configuration module for the code indexer.

This module provides a centralized logging setup using loguru, with configuration
support through environment variables. The logger is automatically configured
when the module is imported and provides colored console output with detailed
formatting.

Environment Variables:
    CODE_INDEX_LOG_LEVEL: Sets the logging level (default: INFO).
        Valid values: DEBUG, INFO, WARNING, ERROR, CRITICAL.

Attributes:
    logger: The configured loguru logger instance used throughout the application.
        This logger provides structured logging with colored output, backtrace
        support, and detailed context information including time, level,
        module, function, and line number.

Example:
    >>> from code_index.utils.logger import logger
    >>> logger.info("Processing started")
    >>> logger.debug("Detailed debug information")
    >>> logger.error("An error occurred")
"""

import os
import sys

from dotenv import load_dotenv
from loguru import logger

__all__ = ["logger"]


def setup_logger():
    """Configure the loguru logger with custom formatting and level settings.

    This function sets up the logger with:
        - Environment-based log level configuration
        - Colored output for better readability
        - Detailed format including timestamp, level, location, and message
        - Backtrace support for better error debugging

    The function loads environment variables from .env files and configures
    the logger to output to stderr with appropriate formatting.
    """
    load_dotenv(override=False)

    log_level = os.getenv("CODE_INDEX_LOG_LEVEL", "INFO").upper()

    # Configure the logger
    logger.remove()  # Remove default handler

    # Add stderr handler with colored output
    logger.add(
        sink=sys.stderr,
        level=log_level,
        backtrace=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )


# Initialize logger configuration when module is imported
setup_logger()

# Emit startup messages to verify logger configuration
logger.debug("Logger debug message")
logger.info("Logger info message")
