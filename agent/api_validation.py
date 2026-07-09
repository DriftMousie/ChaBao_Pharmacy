from __future__ import annotations

from dataclasses import dataclass
import hashlib

from langchain_core.messages import HumanMessage

from agent.model_factory import create_chat_model


@dataclass(frozen=True)
class ApiKeyValidation:
    valid: bool
    code: str
    message: str


def api_key_fingerprint(api_key: str) -> str:
    """只保存不可逆指纹，用于判断密钥是否变化，绝不保存密钥明文。"""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def _friendly_api_error(exc: Exception) -> ApiKeyValidation:
    """兼容 OpenAI SDK 包装异常，不把响应正文或密钥输出到页面。"""
    error_name = type(exc).__name__.lower()
    message = str(exc).lower()
    if "authentication" in error_name or "401" in message or "invalid api key" in message:
        return ApiKeyValidation(False, "AUTH_ERROR", "DeepSeek API Key 无效，请检查后重新输入。")
    if "permission" in error_name or "403" in message:
        return ApiKeyValidation(False, "PERMISSION_ERROR", "当前 API Key 没有访问该模型的权限。")
    if "ratelimit" in error_name or "429" in message or "insufficient balance" in message:
        return ApiKeyValidation(False, "QUOTA_ERROR", "DeepSeek 账户余额不足或请求受限，请检查账户状态。")
    if "timeout" in error_name or "timed out" in message:
        return ApiKeyValidation(False, "TIMEOUT", "连接 DeepSeek 超时，请检查网络后重试。")
    if "connection" in error_name or "connect" in message:
        return ApiKeyValidation(False, "NETWORK_ERROR", "无法连接 DeepSeek，请检查网络。")
    return ApiKeyValidation(False, "API_ERROR", "DeepSeek 验证失败，请检查密钥、网络和账户状态。")


def validate_api_key(api_key: str, model=None) -> ApiKeyValidation:
    """发送最小请求验证密钥；成功响应内容不参与任何业务判断。"""
    if not api_key.strip():
        return ApiKeyValidation(False, "EMPTY_KEY", "请先输入 DeepSeek API Key。")
    validation_model = model or create_chat_model(api_key.strip())
    try:
        validation_model.invoke([HumanMessage(content="仅回复 OK")])
    except Exception as exc:
        return _friendly_api_error(exc)
    return ApiKeyValidation(True, "OK", "DeepSeek API Key 已验证。")

