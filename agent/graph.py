from __future__ import annotations

from typing import Literal, TypedDict
import warnings

from langchain_core._api.deprecation import LangChainPendingDeprecationWarning
from langchain_core.messages import HumanMessage, SystemMessage

# LangGraph 1.1.8 导入缓存/序列化模块时，会由其依赖的 langchain-core
# 触发 allowed_objects 默认值即将变化的 PendingDeprecationWarning。
# 当前项目没有直接使用该序列化入口，因此只过滤这条精确的第三方导入期提示，
# 避免测试和控制台被无关警告干扰，同时保留其他弃用警告。
warnings.filterwarnings(
    "ignore",
    message=r"The default value of `allowed_objects` will change in a future version\.",
    category=LangChainPendingDeprecationWarning,
)

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from agent.model_factory import create_chat_model
from agent.prompts import SYSTEM_PROMPT


IntentName = Literal[
    "create_config",
    "return_offset",
    "sales_medical",
    "medical_sales_detail",
    "prescription_medical",
    "list_files",
    "knowledge",
    "config_ready",
    "confirm",
    "cancel",
    "help",
]


class IntentDecision(BaseModel):
    """限制模型只能选择程序支持的意图，不能生成任意工具名。"""

    intent: IntentName = Field(description="用户当前想执行的操作")
    reason: str = Field(description="一句话说明判断依据")


class ConversationState(TypedDict, total=False):
    user_message: str
    conversation_history: str
    intent: IntentName
    reason: str
    model_error: str


def _fallback_intent(text: str) -> IntentName:
    """网络不可用时仍能识别基础命令，但不会绕过后续确认。"""
    if ("配置" in text or "列名" in text) and any(
        word in text for word in ("好了", "完成", "改好", "修改好", "填好")
    ):
        return "config_ready"
    if "直接使用" in text or "使用现有配置" in text or "用现有配置" in text:
        return "config_ready"
    if any(word in text for word in ("确认", "继续", "开始执行")):
        return "confirm"
    if any(word in text for word in ("取消", "停止")):
        return "cancel"
    # 必须先判断是否在提问，否则“列名配置有什么”会被误判成生成配置。
    if any(word in text for word in ("什么", "哪些", "怎么", "如何", "为什么", "介绍", "说明", "规则", "谁")):
        return "knowledge"
    if "列名" in text or "配置" in text:
        return "create_config"
    if "冲销" in text or "退货" in text:
        return "return_offset"
    if "医保销售明细" in text or ("明细" in text and "医保" in text and "销售" in text):
        return "medical_sales_detail"
    if "处方" in text:
        return "prescription_medical"
    if "串换" in text:
        return "sales_medical"
    if "销售" in text and "医保" in text:
        return "sales_medical"
    if any(word in text for word in ("拷贝", "复制", "放好")) and any(
        word in text for word in ("数据", "文件", "表格", "材料")
    ):
        return "list_files"
    if "文件" in text or "材料" in text:
        return "list_files"
    return "help"


def build_intent_graph(api_key: str):
    model = create_chat_model(api_key).with_structured_output(IntentDecision)

    def classify(state: ConversationState) -> ConversationState:
        text = state["user_message"]
        history = state.get("conversation_history", "无历史对话")
        try:
            decision = model.invoke(
                [
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(
                        content=f"最近十轮对话：\n{history}\n\n用户当前消息：{text}"
                    ),
                ]
            )
            return {"intent": decision.intent, "reason": decision.reason}
        except Exception as exc:
            # 不再静默伪装为正常模型调用；上层会明确提示连接失败。
            return {
                "intent": _fallback_intent(text),
                "reason": f"模型调用失败，已使用本地规则：{type(exc).__name__}",
                "model_error": type(exc).__name__,
            }

    builder = StateGraph(ConversationState)
    builder.add_node("classify", classify)
    builder.add_edge(START, "classify")
    builder.add_edge("classify", END)
    return builder.compile()
