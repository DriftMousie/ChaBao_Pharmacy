from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re


SUPPORTED_SUFFIXES = {".xlsx", ".csv"}
RESULT_MARKERS = ("比对结果", "医保销售比对", "医保处方比对")
RESOURCE_DIR_NAME = "resources"
DEFAULT_CATALOG_NAME = "处方药目录.xlsx"


@dataclass(frozen=True)
class FileInventory:
    sales: list[Path]
    medical: list[Path]
    prescription: list[Path]
    catalog: list[Path]
    configs: list[Path]


def discover_files(workspace: Path) -> FileInventory:
    """只扫描工作目录顶层，避免智能体读取用户未授权的其他目录。"""
    files = [
        path
        for path in workspace.iterdir()
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_SUFFIXES
        and not any(marker in path.stem for marker in RESULT_MARKERS)
    ]
    configs = [path for path in files if "列名配置" in path.stem]
    catalogs = [path for path in files if "处方药目录" in path.stem]
    # 内置处方药目录放在资源目录，避免和用户日常复制/删除的业务文件混在一起。
    # 如果用户仍把处方药目录放在工作目录顶层，也继续兼容识别。
    resource_catalog = workspace / RESOURCE_DIR_NAME / DEFAULT_CATALOG_NAME
    if not catalogs and resource_catalog.is_file():
        catalogs.append(resource_catalog)
    medical = [path for path in files if "医保" in path.stem and path not in catalogs]
    prescription = [
        path
        for path in files
        if "处方" in path.stem and path not in catalogs and path not in medical
    ]
    sales = [
        path
        for path in files
        if path not in configs
        and path not in catalogs
        and path not in medical
        and path not in prescription
        and path.suffix.lower() == ".xlsx"
    ]
    return FileInventory(sales, medical, prescription, catalogs, configs)


def infer_pharmacy_name(*paths: Path) -> str:
    """从文件名提取药店名；仅做保守规则判断，无法确定时使用固定占位名。"""
    markers = (
        "销售端",
        "医保端",
        "处方明细",
        "退货",
        "冲销检查",
        "销售明细",
        "医保",
        "处方",
    )
    for path in paths:
        name = path.stem
        for marker in markers:
            name = name.replace(marker, "")
        name = re.sub(r"[_\-\s]+$", "", name).strip()
        if len(name) >= 2:
            return name
    return "XX药店"


def unique_output_path(
    workspace: Path,
    pharmacy_name: str,
    comparison_name: str,
    suffix: str,
    now: datetime | None = None,
) -> Path:
    """按小时命名；同名时追加序号，保证永不覆盖历史结果。"""
    timestamp = (now or datetime.now()).strftime("%Y%m%d%H")
    base_name = f"{pharmacy_name}_{comparison_name}_{timestamp}"
    candidate = workspace / f"{base_name}{suffix}"
    sequence = 2
    while candidate.exists():
        candidate = workspace / f"{base_name}_{sequence}{suffix}"
        sequence += 1
    return candidate
