from __future__ import annotations

import json
import os
from pathlib import Path


CONFIG_FILE_NAME = "deepseek_config.json"


def load_saved_api_key(config_path: Path) -> tuple[str | None, str | None]:
    """读取本地密钥配置；格式错误时返回提示，不让页面启动失败。"""
    if not config_path.exists():
        return None, None
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        api_key = str(payload.get("deepseek_api_key", "")).strip()
    except (OSError, json.JSONDecodeError, AttributeError) as exc:
        return None, f"密钥配置文件无法读取：{type(exc).__name__}"
    if not api_key:
        return None, "密钥配置文件中没有有效的 DeepSeek API Key。"
    return api_key, None


def save_api_key(config_path: Path, api_key: str) -> None:
    """验证成功后原子写入 JSON，并尽量限制为当前系统用户读写。"""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = config_path.with_suffix(config_path.suffix + ".tmp")
    payload = {"deepseek_api_key": api_key.strip()}
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    try:
        os.chmod(temporary_path, 0o600)
    except OSError:
        # Windows 上 chmod 语义有限，最终安装版应再结合用户目录 ACL。
        pass
    temporary_path.replace(config_path)

