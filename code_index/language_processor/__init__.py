from typing import Optional

from .base import QueryContext, LanguageProcessor
from .impl_c import CProcessor
from .impl_cpp import CppProcessor
from .impl_python import PythonProcessor


def language_processor_factory(name: str) -> Optional[LanguageProcessor]:
    """
    一个简单的工厂函数，根据语言名称返回对应的处理器实例。
    """
    processors = {
        "python": PythonProcessor,
        "c": CProcessor,
        "cpp": CppProcessor,
    }
    processor_class = processors.get(name)
    if processor_class:
        return processor_class()

    print(f"Warning: No language processor found for '{name}'")
    return None
