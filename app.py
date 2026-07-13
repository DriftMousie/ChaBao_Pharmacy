from __future__ import annotations

from pathlib import Path
import os
import platform
import subprocess

import streamlit as st

from agent.controller import AgentSession, InspectionAgent
from agent.api_validation import api_key_fingerprint, validate_api_key
from services.settings import CONFIG_FILE_NAME, load_saved_api_key, save_api_key
from services.knowledge import load_welcome_message


APP_ROOT = Path(__file__).resolve().parent
WORKSPACE = Path(os.environ.get("CHABAO_WORKSPACE", APP_ROOT)).expanduser().resolve()
WORKSPACE.mkdir(parents=True, exist_ok=True)
API_CONFIG_PATH = WORKSPACE / CONFIG_FILE_NAME
ASSISTANT_AVATAR_PATH = APP_ROOT / "resources" / "image.jpg"
ASSISTANT_AVATAR = str(ASSISTANT_AVATAR_PATH) if ASSISTANT_AVATAR_PATH.exists() else "assistant"
APP_TITLE = "查宝（药店版）"
APP_SUBTITLE = "designed by DriftMousie"


def _open_workspace() -> tuple[bool, str]:
    """打开用户业务工作目录，方便非技术用户放文件和找结果。"""
    try:
        system = platform.system()
        if system == "Windows":
            subprocess.Popen(["explorer", str(WORKSPACE)])
        elif system == "Darwin":
            subprocess.Popen(["open", str(WORKSPACE)])
        else:
            subprocess.Popen(["xdg-open", str(WORKSPACE)])
    except Exception as exc:
        return False, f"无法自动打开工作目录，请手动打开：{WORKSPACE}（{exc}）"
    return True, "已请求系统打开工作目录。"


def _open_local_file(path: Path) -> tuple[bool, str]:
    """只允许打开工作目录内的结果，避免模型传入任意系统路径。"""
    resolved = path.resolve()
    if WORKSPACE.resolve() not in resolved.parents:
        return False, "出于安全原因，只能打开工作目录中的文件。"
    if not resolved.exists():
        return False, "结果文件已经不存在，请重新执行检查。"
    try:
        system = platform.system()
        if system == "Windows":
            subprocess.Popen(["explorer", str(resolved)])
        elif system == "Darwin":
            subprocess.Popen(["open", str(resolved)])
        else:
            subprocess.Popen(["xdg-open", str(resolved)])
    except Exception as exc:
        return False, f"无法自动打开文件，请手动打开：{resolved}（{exc}）"
    return True, "已请求系统打开结果文件。"


def _save_uploaded_files(files: list) -> list[str]:
    saved = []
    for uploaded in files:
        # Path.name 会丢弃上传文件中可能携带的目录部分。
        safe_name = Path(uploaded.name).name
        destination = WORKSPACE / safe_name
        destination.write_bytes(uploaded.getvalue())
        saved.append(safe_name)
    return saved


def _initialize_state() -> None:
    if "agent_session" not in st.session_state:
        st.session_state.agent_session = AgentSession()
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = [
            {
                "role": "assistant",
                "content": "请先填写 DeepSeek API Key，并点击“保存并验证密钥”。验证成功后我会为您介绍使用方法。",
                "output_files": [],
            }
        ]
    if "welcome_sent" not in st.session_state:
        st.session_state.welcome_sent = False
    if "is_processing" not in st.session_state:
        st.session_state.is_processing = False
    if "saved_key_checked" not in st.session_state:
        saved_key, load_error = load_saved_api_key(API_CONFIG_PATH)
        st.session_state.saved_key_checked = True
        if saved_key:
            st.session_state.deepseek_api_key = saved_key
            st.session_state.saved_key_needs_validation = True
        elif load_error:
            st.session_state.chat_messages.append(
                {
                    "role": "assistant",
                    "content": f"发现本地密钥配置，但读取失败：{load_error} 请重新输入并保存。",
                    "output_files": [],
                }
            )


def _recover_stale_processing_state() -> None:
    """新一轮脚本运行时清理上一次被中断后遗留的执行锁。"""
    if not st.session_state.get("is_processing", False) or st.session_state.get(
        "queued_submission"
    ):
        return
    st.session_state.is_processing = False
    session = st.session_state.get("agent_session")
    if session is not None:
        session.is_processing = False
    st.session_state.chat_messages.append(
        {
            "role": "assistant",
            "content": (
                "检测到上一次任务留下的执行状态，输入框已经恢复。"
                "如果结果文件已经生成，可以输入“查看当前文件”；否则请重新执行任务。"
            ),
            "output_files": [],
        }
    )


def _render_message(message: dict) -> None:
    avatar = ASSISTANT_AVATAR if message["role"] == "assistant" else None
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])
        for raw_path in message.get("output_files", []):
            path = Path(raw_path)
            if st.button(f"打开结果文件：{path.name}", key=f"open-{len(st.session_state.chat_messages)}-{path}"):
                success, text = _open_local_file(path)
                (st.success if success else st.error)(text)


st.set_page_config(page_title=f"{APP_TITLE} {APP_SUBTITLE}", page_icon="💊", layout="centered")
st.markdown(
    """
    <style>
    .block-container {max-width: 860px; padding-top: 2rem;}
    [data-testid="stHeader"] {background: transparent;}
    .chabao-title {text-align: center; margin-bottom: 0.25rem;}
    .chabao-title h1 {font-size: 2.2rem; margin-bottom: 0.2rem;}
    .chabao-title p {color: #6b7280; font-size: 0.95rem; margin-top: 0;}
    </style>
    """,
    unsafe_allow_html=True,
)

_initialize_state()
_recover_stale_processing_state()
st.markdown(
    f"""
    <div class="chabao-title">
        <h1>{APP_TITLE}</h1>
        <p>{APP_SUBTITLE}</p>
    </div>
    """,
    unsafe_allow_html=True,
)
workspace_col, open_workspace_col = st.columns([0.76, 0.24])
with workspace_col:
    st.caption(f"本地工作目录：{WORKSPACE}")
with open_workspace_col:
    if st.button("打开工作目录", use_container_width=True):
        success, text = _open_workspace()
        (st.success if success else st.error)(text)

# 密钥只进入当前 WebSocket 对应的 Session State，不写入配置文件。
api_key = st.text_input(
    "DeepSeek API Key",
    type="password",
    key="deepseek_api_key",
    placeholder="请输入 API Key",
)

# 用户主动点击后才验证并保存；从 JSON 加载的密钥在启动时自动重新验证。
save_key_clicked = st.button("保存并验证密钥", type="primary", use_container_width=True)
api_key_is_valid = False
if save_key_clicked and not api_key.strip():
    st.session_state.chat_messages.append(
        {
            "role": "assistant",
            "content": "还没有输入 DeepSeek API Key，请先填写密钥再点击保存。",
            "output_files": [],
        }
    )
if api_key.strip():
    fingerprint = api_key_fingerprint(api_key.strip())
    cached_validation = st.session_state.get("api_key_validation")
    should_validate = save_key_clicked or st.session_state.pop(
        "saved_key_needs_validation",
        False,
    )
    if should_validate:
        with st.spinner("正在验证 DeepSeek API Key..."):
            validation = validate_api_key(api_key.strip())
        st.session_state.api_key_validation = {
            "fingerprint": fingerprint,
            "valid": validation.valid,
            "message": validation.message,
        }
        if validation.valid:
            try:
                save_api_key(API_CONFIG_PATH, api_key.strip())
                validation_message = "DeepSeek API Key 验证成功，已保存到本地配置。"
            except OSError as exc:
                validation_message = f"API Key 验证成功，但保存失败：{exc}"
            st.session_state.chat_messages.append(
                {"role": "assistant", "content": validation_message, "output_files": []}
            )
            if not st.session_state.welcome_sent:
                st.session_state.chat_messages.append(
                    {
                        "role": "assistant",
                        "content": load_welcome_message(APP_ROOT / "knowledge"),
                        "output_files": [],
                    }
                )
                st.session_state.welcome_sent = True
        else:
            st.session_state.chat_messages.append(
                {"role": "assistant", "content": validation.message, "output_files": []}
            )
    cached_validation = st.session_state.get("api_key_validation")
    if cached_validation and cached_validation["fingerprint"] == fingerprint:
        api_key_is_valid = bool(cached_validation["valid"])
    if api_key_is_valid:
        st.success("DeepSeek API Key 已验证，可以开始对话。", icon="✅")
    else:
        st.info("输入或修改密钥后，请点击“保存并验证密钥”。", icon="ℹ️")

for chat_message in st.session_state.chat_messages:
    _render_message(chat_message)

is_processing = bool(st.session_state.get("is_processing", False))
if is_processing:
    st.warning("正在执行数据处理，请不要关闭窗口，也不要重复提交指令。大文件可能需要几分钟，完成后我会显示结果文件。", icon="⏳")

queued_submission = st.session_state.pop("queued_submission", None)
if queued_submission:
    user_text = queued_submission["user_text"]
    result = None
    try:
        with st.status("正在执行数据处理，请勿重复提交。大文件可能需要几分钟...", expanded=True) as status:
            st.write("请保持此窗口打开。任务完成后，我会显示结果文件和下一步建议。")
            agent = InspectionAgent(WORKSPACE, api_key.strip(), st.session_state.agent_session)
            reply, result = agent.handle(user_text, ignore_processing_lock=True)
            # 最近十轮问答进入智能体短期记忆，下一次判断会结合上下文。
            st.session_state.agent_session.remember(user_text, reply)
            status.update(label="处理完成", state="complete", expanded=False)
    except Exception as exc:
        reply = f"任务执行时出现异常：{exc}。请检查输入文件后重试。"
    finally:
        st.session_state.agent_session.is_processing = False
        st.session_state.is_processing = False

    st.session_state.chat_messages.append(
        {
            "role": "assistant",
            "content": reply,
            "output_files": [str(path) for path in result.output_files] if result else [],
        }
    )
    st.rerun()

submission = st.chat_input(
    "正在执行任务，请等待完成..." if is_processing else "输入需求或附加 Excel/CSV 文件",
    accept_file="multiple",
    file_type=["xlsx", "csv"],
    disabled=not api_key_is_valid or is_processing,
)

if submission:
    if isinstance(submission, str):
        user_text = submission
        uploaded_files = []
    else:
        user_text = submission.text or "请检查我刚上传的文件"
        uploaded_files = list(submission.files)

    saved_names = _save_uploaded_files(uploaded_files)
    shown_text = user_text
    if saved_names:
        shown_text += "\n\n已附加：" + "、".join(saved_names)
    st.session_state.chat_messages.append(
        {"role": "user", "content": shown_text, "output_files": []}
    )

    st.session_state.queued_submission = {"user_text": user_text}
    st.session_state.is_processing = True
    st.session_state.agent_session.is_processing = True
    st.rerun()
