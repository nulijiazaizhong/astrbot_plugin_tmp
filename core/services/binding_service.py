"""core.services.binding_service

维护"AstrBot 用户 ID <-> TMP ID"绑定关系，持久化到 JSON 文件。

数据格式：

.. code-block:: json

    {
        "<user_id>": {
            "tmp_id": "123",
            "player_name": "xxx",
            "bind_time": 1735680000.0
        }
    """

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional


class BindingService:
    """简单的 JSON 持久化绑定存储。"""

    DEFAULT_FILE = "tmp_bindings.json"

    def __init__(self, file_path: Optional[str] = None) -> None:
        self.file_path = file_path or self.DEFAULT_FILE
        # 确保父目录存在
        Path(self.file_path).parent.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Any] = self._load()

    # ------------------------------------------------------------------ #
    # 持久化
    # ------------------------------------------------------------------ #
    def _load(self) -> Dict[str, Any]:
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    if isinstance(data, dict):
                        return data
        except Exception:
            pass
        return {}

    def _save(self) -> None:
        try:
            with open(self.file_path, "w", encoding="utf-8") as fh:
                json.dump(self._cache, fh, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #
    def get(self, user_id: str) -> Optional[str]:
        """读取用户已绑定的 TMP ID。"""
        rec = self._cache.get(user_id)
        if isinstance(rec, dict):
            return rec.get("tmp_id")
        return rec

    def bind(self, user_id: str, tmp_id: str, player_name: str = "") -> bool:
        """绑定 ``user_id`` 与 ``tmp_id``。"""
        self._cache[user_id] = {
            "tmp_id": str(tmp_id),
            "player_name": player_name,
            "bind_time": time.time(),
        }
        return self._save()

    def unbind(self, user_id: str) -> bool:
        """解除 ``user_id`` 的绑定。返回是否真删除了条目。"""
        if user_id in self._cache:
            del self._cache[user_id]
            self._save()
            return True
        return False

    def all(self) -> Dict[str, Any]:
        return dict(self._cache)


__all__ = ["BindingService"]
