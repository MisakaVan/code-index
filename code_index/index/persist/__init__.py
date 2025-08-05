"""Implementation of persistence mechanisms for the code index module.

This module provides different strategies to persist the indexed data.
The available strategies include JSON (dumping to a single JSON file)
and SQLite (storing data in a SQLite database).

"""

from .persist_json import SingleJsonFilePersistStrategy
from .persist_sqlite import SqlitePersistStrategy
