from pathlib import Path
import json

from .base import BaseIndex, PersistStrategy
from ..models import (
    CodeLocation,
    Definition,
    Reference,
    FunctionLikeInfo,
    FunctionLike,
    Function,
    Method,
)
from ..utils.custom_json import EnhancedJSONEncoder, custom_json_decoder


class SingleJsonFilePersistStrategy(PersistStrategy):
    """
    单个 JSON 文件持久化策略。
    """

    def __init__(self):
        super().__init__()

    def save(self, data: dict, path: Path):
        pass

    def load(self, path: Path) -> dict:
        pass
