"""锁文件 ``道.锁``：记录依赖的精确版本与安装来源。

格式为一个 UTF-8 JSON 文件（中文键名，与 ``道.配置`` 风格一致）::

    {
      "版本": 1,
      "包": {
        "数学库": {
          "版本": "1.2.0",
          "来源": "/abs/path/数学库-1.2.0.道包",
          "校验": "sha256:...."
        }
      }
    }

``来源`` 可以是 ``.道包`` 归档路径，也可以是本地仓库中的归档路径；安装时
优先按锁文件记录的版本与来源安装，从而避免依赖漂移。
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from .version import Version

LOCK_FILENAME = "道.锁"
LOCK_VERSION = 1


class LockDriftError(RuntimeError):
    """锁文件记录的版本与实际要安装的版本不一致。"""

    def __init__(self, name: str, locked: Version, actual: Version):
        self.name = name
        self.locked = locked
        self.actual = actual
        super().__init__(
            f"版本漂移：锁文件 {LOCK_FILENAME} 记录 '{name}' 为 {locked}，"
            f"实际为 {actual}。请先更新锁文件（--update-lock）再安装。"
        )


def sha256_file(path: str | os.PathLike[str]) -> str:
    """计算文件 SHA-256，返回 ``sha256:<hex>`` 形式的校验串。"""
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


@dataclass
class LockedPackage:
    name: str
    version: Version
    source: str = ""
    checksum: str = ""

    def to_dict(self) -> dict:
        return {
            "版本": str(self.version),
            "来源": self.source,
            "校验": self.checksum,
        }

    @classmethod
    def from_dict(cls, name: str, data: dict) -> LockedPackage:
        version_text = data.get("版本")
        if not version_text:
            raise ValueError(f"锁文件中 '{name}' 缺少「版本」")
        return cls(
            name=name,
            version=Version.parse(str(version_text)),
            source=str(data.get("来源", "")),
            checksum=str(data.get("校验", "")),
        )

    def __str__(self) -> str:
        return f"{self.name} {self.version}"


class LockFile:
    """读写项目根目录下的 ``道.锁``。"""

    def __init__(self, project_dir: str | os.PathLike[str] | None = None, path=None):
        base = Path(project_dir) if project_dir is not None else Path.cwd()
        self.project_dir = base
        self.path = Path(path) if path is not None else base / LOCK_FILENAME
        self._data: dict | None = None

    @property
    def exists(self) -> bool:
        return self.path.is_file()

    @property
    def data(self) -> dict:
        if self._data is None:
            self._data = self._load()
        return self._data

    def _load(self) -> dict:
        if not self.path.is_file():
            return {"版本": LOCK_VERSION, "包": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"锁文件 {self.path} 读取失败或格式损坏：{exc}") from exc
        if not isinstance(data, dict):
            raise TypeError(f"锁文件 {self.path} 格式错误：顶层必须是对象")
        version = data.get("版本", LOCK_VERSION)
        if version != LOCK_VERSION:
            raise ValueError(
                f"锁文件 {self.path} 版本 {version} 不兼容，当前支持版本 {LOCK_VERSION}"
            )
        packages = data.get("包", {})
        if not isinstance(packages, dict):
            raise TypeError(f"锁文件 {self.path} 格式错误：「包」必须是对象")
        data["版本"] = version
        data["包"] = packages
        return data

    def save(self) -> str:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(self.data, ensure_ascii=False, indent=2) + "\n"
        self.path.write_text(text, encoding="utf-8")
        return str(self.path)

    def entries(self) -> dict[str, LockedPackage]:
        return {
            name: LockedPackage.from_dict(name, value)
            for name, value in self.data["包"].items()
        }

    def get(self, name: str) -> LockedPackage | None:
        raw = self.data["包"].get(name)
        return LockedPackage.from_dict(name, raw) if raw else None

    def set(
        self,
        name: str,
        version: Version,
        source: str = "",
        checksum: str = "",
    ) -> LockedPackage:
        entry = LockedPackage(name=name, version=version, source=source, checksum=checksum)
        self.data["包"][name] = entry.to_dict()
        self.save()
        return entry

    def remove(self, name: str) -> bool:
        removed = self.data["包"].pop(name, None) is not None
        if removed:
            self.save()
        return removed

    def is_empty(self) -> bool:
        return not self.data["包"]

    def check(self, name: str, version: Version) -> None:
        """校验版本是否与锁文件一致，漂移时抛 :class:`LockDriftError`。"""
        locked = self.get(name)
        if locked is not None and locked.version != version:
            raise LockDriftError(name, locked.version, version)

    def __str__(self) -> str:
        lines = [f"版本 {LOCK_VERSION}"]
        for entry in self.entries().values():
            source = f" 来源 {entry.source}" if entry.source else ""
            lines.append(f"    {entry.name} {entry.version}{source}")
        return "\n".join(lines)
