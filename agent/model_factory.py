from __future__ import annotations

from langchain_deepseek import ChatDeepSeek


def create_chat_model(api_key: str) -> ChatDeepSeek:
    """密钥仅从当前调用传入，不读取环境变量，也不写入持久状态。"""
    return ChatDeepSeek(
        model="deepseek-v4-flash",
        api_key=api_key,
        base_url="https://api.deepseek.com",
        temperature=0,
        max_retries=1,
        timeout=30,
        extra_body={"thinking": {"type": "disabled"}},
    )

