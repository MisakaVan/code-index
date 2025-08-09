import json
from pathlib import Path
from typing import Any

from ..base import PersistStrategy
from ...utils.logger import logger
from ...models import IndexData


class SingleJsonFilePersistStrategy(PersistStrategy):
    """JSON file persistence strategy for index data.

    Saves and loads index data to/from a single JSON file using custom
    serialization for dataclass objects and complex types.
    """

    def __init__(self):
        """Initializes the JSON persistence strategy."""
        super().__init__()

    def __repr__(self) -> str:
        """Returns a string representation of the persistence strategy."""
        return f"{self.__class__.__name__}()"

    def save(self, data: IndexData, path: Path):
        """Saves index data to a JSON file.

        Args:
            data: The index data object to save.
            path: The file path where data will be saved.

        Raises:
            ValueError: If path is a directory or parent directory issues.
            FileNotFoundError: If parent directory doesn't exist.
            RuntimeError: If saving fails due to other errors.
        """
        # Check if path points to a directory
        if path.exists() and path.is_dir():
            raise ValueError(f"Specified path is a directory, not a file: {path}")

        # Check if parent directory exists
        parent_dir = path.parent
        if not parent_dir.exists():
            raise FileNotFoundError(
                f"Parent directory does not exist: {parent_dir}. Please create the directory first."
            )

        # Check if parent directory is writable
        if not parent_dir.is_dir():
            raise ValueError(f"Parent path is not a directory: {parent_dir}")

        try:
            # dump_index_to_json(data, path)
            dumped_json_str = data.model_dump_json(indent=2)
            path.write_text(dumped_json_str, encoding="utf-8")
        except Exception as e:
            raise RuntimeError(f"Error saving index data to file {path}: {e}")

    def load(self, path: Path) -> IndexData:
        """Loads index data from a JSON file.

        Args:
            path: The JSON file path to load from.

        Returns:
            The loaded index data.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If path is a directory or not a regular file.
            json.JSONDecodeError: If file is not valid JSON.
            RuntimeError: If loading fails due to other errors.
        """
        # Check if file exists
        if not path.exists():
            raise FileNotFoundError(f"Index file does not exist: {path}")

        # Check if path points to a directory
        if path.is_dir():
            raise ValueError(f"Specified path is a directory, not a file: {path}")

        # Check if it's a regular file
        if not path.is_file():
            raise ValueError(f"Path exists but is not a regular file: {path}")

        try:
            json_str = path.read_text(encoding="utf-8")
            return IndexData.model_validate_json(json_str)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(f"File {path} is not valid JSON: {e.msg}", e.doc, e.pos)
        except Exception as e:
            raise RuntimeError(f"Error loading index file {path}: {e}")
