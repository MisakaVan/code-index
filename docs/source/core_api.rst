Core API Reference
==================

This section contains the main components of the code-index library.

Main Classes
------------

CodeIndexer
~~~~~~~~~~~

.. autoclass:: code_index.indexer.CodeIndexer
   :members:
   :member-order: bysource
   :no-index:

Command Line Interface
----------------------

The code-index library provides a command-line interface for indexing source code repositories.

.. automodule:: code_index.__main__
   :members:

Command Usage
~~~~~~~~~~~~~

Use the command-line tool to index source code repositories:

.. code-block:: bash

   # View all available options
   uv run -m code_index --help

   # Basic usage example
   code-index /path/to/repository --language python --dump-type json

Data Models
-----------

.. automodule:: code_index.models
   :members:
   :member-order: bysource
   :exclude-members: __weakref__
   :no-index:

Configuration
-------------

.. automodule:: code_index.config
   :members:
