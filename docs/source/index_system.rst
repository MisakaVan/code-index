Index System
============

The index system provides various implementations for storing and querying code symbols.

Base Classes
------------

.. automodule:: code_index.index.base

.. autoclass:: code_index.index.base.BaseIndex
   :members:
   :show-inheritance:
   :undoc-members:

.. autoclass:: code_index.index.base.PersistStrategy
   :members:
   :show-inheritance:
   :undoc-members:


Query Interface
---------------

.. automodule:: code_index.index.code_query
   :members:
   :show-inheritance:
   :undoc-members:


Index Implementations
---------------------

.. autoclass:: code_index.index.impl.simple_index.SimpleIndex
   :members:
   :show-inheritance:
   :undoc-members:


Persistence Backends
--------------------

.. automodule:: code_index.index.persist.__init__


.. autoclass:: code_index.index.persist.SingleJsonFilePersistStrategy
    :members:
    :show-inheritance:
    :undoc-members:


.. autoclass:: code_index.index.persist.SqlitePersistStrategy
    :members:
    :show-inheritance:
    :undoc-members:
