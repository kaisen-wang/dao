from __future__ import annotations

import re


class Version:
    __slots__ = ("major", "minor", "patch", "pre_release", "build")

    def __init__(
        self,
        major: int = 0,
        minor: int = 0,
        patch: int = 0,
        pre_release: str | None = None,
        build: str | None = None,
    ):
        self.major = major
        self.minor = minor
        self.patch = patch
        self.pre_release = pre_release
        self.build = build

    @classmethod
    def parse(cls, version_str: str) -> Version:
        version_str = version_str.strip()
        match = re.match(
            r"^(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9.]+))?(?:\+([a-zA-Z0-9.]+))?$",
            version_str,
        )
        if not match:
            raise ValueError(f"无效的版本号格式: '{version_str}'")
        return cls(
            major=int(match.group(1)),
            minor=int(match.group(2)),
            patch=int(match.group(3)),
            pre_release=match.group(4),
            build=match.group(5),
        )

    def __str__(self) -> str:
        result = f"{self.major}.{self.minor}.{self.patch}"
        if self.pre_release:
            result += f"-{self.pre_release}"
        if self.build:
            result += f"+{self.build}"
        return result

    def __repr__(self) -> str:
        return f"Version('{self}')"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return (
            self.major == other.major
            and self.minor == other.minor
            and self.patch == other.patch
            and self.pre_release == other.pre_release
        )

    def __lt__(self, other: Version) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        if (self.major, self.minor, self.patch) != (other.major, other.minor, other.patch):
            return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)
        if self.pre_release is None and other.pre_release is not None:
            return False
        if self.pre_release is not None and other.pre_release is None:
            return True
        if self.pre_release is not None and other.pre_release is not None:
            return self.pre_release < other.pre_release
        return False

    def __le__(self, other: Version) -> bool:
        return self == other or self < other

    def __gt__(self, other: Version) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return not self <= other

    def __ge__(self, other: Version) -> bool:
        return self == other or self > other

    def __hash__(self) -> int:
        return hash((self.major, self.minor, self.patch, self.pre_release))


class VersionConstraint:
    def __init__(self, operator: str, version: Version):
        self.operator = operator
        self.version = version

    @classmethod
    def parse(cls, constraint_str: str) -> VersionConstraint:
        constraint_str = constraint_str.strip()
        if constraint_str.startswith(">="):
            return cls(">=", Version.parse(constraint_str[2:]))
        elif constraint_str.startswith("<="):
            return cls("<=", Version.parse(constraint_str[2:]))
        elif constraint_str.startswith("^"):
            return cls("^", Version.parse(constraint_str[1:]))
        elif constraint_str.startswith("~"):
            return cls("~", Version.parse(constraint_str[1:]))
        elif constraint_str.startswith(">"):
            return cls(">", Version.parse(constraint_str[1:]))
        elif constraint_str.startswith("<"):
            return cls("<", Version.parse(constraint_str[1:]))
        else:
            return cls("==", Version.parse(constraint_str))

    def matches(self, version: Version) -> bool:
        if self.operator == "==":
            return version == self.version
        elif self.operator == ">=":
            return version >= self.version
        elif self.operator == "<=":
            return version <= self.version
        elif self.operator == ">":
            return version > self.version
        elif self.operator == "<":
            return version < self.version
        elif self.operator == "^":
            if version.major != self.version.major:
                return False
            if version.major == 0:
                return version.minor == self.version.minor and version >= self.version
            return version >= self.version and version.major == self.version.major
        elif self.operator == "~":
            if version.major != self.version.major or version.minor != self.version.minor:
                return False
            return version >= self.version
        return False

    def __str__(self) -> str:
        return f"{self.operator}{self.version}"

    def __repr__(self) -> str:
        return f"VersionConstraint('{self}')"