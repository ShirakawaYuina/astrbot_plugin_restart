import os
from pathlib import Path


def pytest_configure():
    """测试时固定 AstrBot 根目录，避免在插件目录生成运行时 data 目录。"""
    repo_root = Path(__file__).resolve().parents[4]
    os.environ.setdefault("ASTRBOT_ROOT", str(repo_root))
