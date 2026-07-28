from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class CompareMode(str, Enum):
    STRICT = "strict"
    SEMANTIC = "semantic"
    AUTO = "auto"


@dataclass(frozen=True)
class ComparisonOptions:
    mode: CompareMode = CompareMode.STRICT
    max_differences: int = 100
    block_size: int = 1024 * 1024
    ignore_case: bool = False
    ignore_whitespace: bool = False
    ignore_line_endings: bool = False
    generate_visual_diff: bool = False
    exclusions: tuple[str, ...] = ()


@dataclass
class Difference:
    kind: str
    location: str
    left: Any = None
    right: Any = None
    detail: str = ""


@dataclass
class ComparisonResult:
    left_path: str
    right_path: str
    detected_type: str = "unknown"
    left_size: int | None = None
    right_size: int | None = None
    left_sha256: str | None = None
    right_sha256: str | None = None
    strict_equal: bool | None = None
    semantic_equal: bool | None = None
    method: str = ""
    elapsed_seconds: float = 0.0
    differences: list[Difference] = field(default_factory=list)
    total_differences: int = 0
    truncated: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def equal(self) -> bool | None:
        return self.strict_equal

    def add_difference(self, difference: Difference, maximum: int) -> None:
        self.total_differences += 1
        if len(self.differences) < maximum:
            self.differences.append(difference)
        else:
            self.truncated = True

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["left_path"] = str(Path(self.left_path))
        data["right_path"] = str(Path(self.right_path))
        return data
