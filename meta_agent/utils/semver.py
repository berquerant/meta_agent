"""Semantic versioning utilities."""

from dataclasses import dataclass
import re


@dataclass
class SemVer:
    """Semantic version representation (major.minor.patch)."""

    major: int = 0
    minor: int = 1
    patch: int = 0

    @classmethod
    def parse(cls, version_str: str) -> "SemVer":
        """Parse version string into SemVer."""
        m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", version_str.strip())
        if not m:
            return cls(0, 1, 0)
        major = int(m.group(1))
        minor = int(m.group(2))
        patch = int(m.group(3)) if m.group(3) is not None else 0
        return cls(major, minor, patch)

    def bump_patch(self) -> "SemVer":
        """Bump patch version."""
        return SemVer(self.major, self.minor, self.patch + 1)

    def bump_minor(self) -> "SemVer":
        """Bump minor version."""
        return SemVer(self.major, self.minor + 1, 0)

    def __str__(self) -> str:
        """Return formatted semver string."""
        return f"{self.major}.{self.minor}.{self.patch}"

    def to_suffix(self) -> str:
        """Return filename-safe suffix (e.g. v0-2-0)."""
        return f"v{self.major}-{self.minor}-{self.patch}"
