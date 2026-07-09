from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ToolResult:
    """所有业务工具统一返回该结构，避免 UI 依赖具体分析函数。"""

    success: bool
    operation: str
    message: str
    statistics: dict[str, Any] = field(default_factory=dict)
    output_files: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class UserFacingError:
    """保留技术详情供本地排查，同时给普通用户提供可执行建议。"""

    error_code: str
    stage: str
    technical_message: str
    user_message: str
    suggestions: list[str] = field(default_factory=list)

