# code_index/config.py
from pathlib import Path

# Path(__file__) -> my_project/code_index/config.py
# .parent -> my_project/code_index
# .parent -> my_project (项目根目录)
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

BUILD_DIR = PROJECT_ROOT / "build"
