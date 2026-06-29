from __future__ import annotations

from dataclasses import dataclass, field

from .version import Version, VersionConstraint


@dataclass
class Dependency:
    name: str
    constraint: VersionConstraint | None = None
    is_dev: bool = False

    @classmethod
    def parse(cls, dep_str: str, is_dev: bool = False) -> Dependency:
        dep_str = dep_str.strip()
        parts = dep_str.split(None, 1)
        name = parts[0]
        constraint = None
        if len(parts) > 1:
            constraint = VersionConstraint.parse(parts[1])
        return cls(name=name, constraint=constraint, is_dev=is_dev)

    def __str__(self) -> str:
        if self.constraint:
            return f"{self.name} {self.constraint}"
        return self.name


@dataclass
class PackageConfig:
    name: str = ""
    version: Version | None = None
    author: str = ""
    description: str = ""
    entry: str = ""
    dependencies: list[Dependency] = field(default_factory=list)
    dev_dependencies: list[Dependency] = field(default_factory=list)

    @classmethod
    def parse(cls, content: str) -> PackageConfig:
        lines = content.strip().splitlines()
        config = cls()
        current_section = None

        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith("//"):
                continue

            if line in ("依赖", "开发依赖"):
                current_section = "dev_deps" if line == "开发依赖" else "deps"
                continue

            if current_section is None:
                parts = line.split(None, 1)
                key = parts[0]
                value = parts[1] if len(parts) > 1 else ""

                if key == "名称":
                    config.name = value
                elif key == "版本":
                    config.version = Version.parse(value)
                elif key == "作者":
                    config.author = value
                elif key == "描述":
                    config.description = value
                elif key == "入口":
                    config.entry = value
            elif current_section == "deps":
                dep = Dependency.parse(line, is_dev=False)
                config.dependencies.append(dep)
            elif current_section == "dev_deps":
                dep = Dependency.parse(line, is_dev=True)
                config.dev_dependencies.append(dep)

        return config

    @classmethod
    def from_file(cls, filepath: str) -> PackageConfig:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return cls.parse(content)

    def __str__(self) -> str:
        lines = []
        if self.name:
            lines.append(f"名称 {self.name}")
        if self.version:
            lines.append(f"版本 {self.version}")
        if self.author:
            lines.append(f"作者 {self.author}")
        if self.description:
            lines.append(f"描述 {self.description}")
        if self.entry:
            lines.append(f"入口 {self.entry}")
        if self.dependencies:
            lines.append("依赖")
            for dep in self.dependencies:
                lines.append(f"    {dep}")
        if self.dev_dependencies:
            lines.append("开发依赖")
            for dep in self.dev_dependencies:
                lines.append(f"    {dep}")
        return "\n".join(lines)