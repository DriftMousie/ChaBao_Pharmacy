from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from agent.graph import IntentName, _fallback_intent, build_intent_graph
from agent.model_factory import create_chat_model
from agent.prompts import GENERAL_CHAT_PROMPT, KNOWLEDGE_ANSWER_PROMPT
from models.results import ToolResult
from services.analysis_tools import (
    check_returns,
    compare_prescriptions,
    compare_sales,
    create_config,
    screen_medical_sales_details,
)
from services.files import discover_files, infer_pharmacy_name, unique_output_path
from services.knowledge import KnowledgeBase
from pharmacy_analysis import load_column_config


MAX_MEMORY_ROUNDS = 10
MAX_MEMORY_MESSAGES = MAX_MEMORY_ROUNDS * 2


@dataclass
class PendingAction:
    name: str
    arguments: dict[str, Path]
    summary: str


@dataclass
class AgentSession:
    """该对象只保存在 Streamlit 会话中，不包含 API Key。"""

    pending_action: PendingAction | None = None
    return_output: Path | None = None
    last_operation: str | None = None
    is_processing: bool = False
    messages: list[dict[str, str]] = field(default_factory=list)
    warnings_shown: set[str] = field(default_factory=set)

    def remember(self, user_message: str, assistant_message: str) -> None:
        """只保留最近十轮问答，兼顾上下文连续性和 API 消耗。"""
        self.messages.extend(
            [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_message},
            ]
        )
        self.messages = self.messages[-MAX_MEMORY_MESSAGES:]

    def history_text(self) -> str:
        role_names = {"user": "用户", "assistant": "查宝"}
        return "\n".join(
            f"{role_names.get(item['role'], item['role'])}：{item['content']}"
            for item in self.messages
        ) or "无历史对话"


class InspectionAgent:
    def __init__(self, workspace: Path, api_key: str, session: AgentSession):
        self.workspace = workspace.resolve()
        self.session = session
        self.graph = build_intent_graph(api_key)
        self.model = create_chat_model(api_key)
        self.knowledge_base = KnowledgeBase(self.workspace / "knowledge")

    def handle(
        self, user_message: str, ignore_processing_lock: bool = False
    ) -> tuple[str, ToolResult | None]:
        if self.session.is_processing and not ignore_processing_lock:
            return (
                "当前已有任务正在执行，请等待完成后再输入新指令。"
                "处理大文件可能需要几分钟，请不要重复提交。",
                None,
            )
        reply, result = self._handle_raw(user_message)
        return self._append_next_input_suggestion(reply), result

    def _handle_raw(self, user_message: str) -> tuple[str, ToolResult | None]:
        # 明确业务指令必须优先走本地规则，不能再交给模型二次判断。
        # 否则“确认”可能被模型误判为重新发起上一步，导致待确认操作无法执行。
        # 只有本地规则无法判断的闲聊或模糊表达才进入 LangGraph/DeepSeek。
        local_intent = _fallback_intent(user_message)
        if local_intent != "help":
            intent: IntentName = local_intent
        else:
            decision = self.graph.invoke(
                {
                    "user_message": user_message,
                    "conversation_history": self.session.history_text(),
                }
            )
            if decision.get("model_error"):
                return (
                    "DeepSeek 本次调用失败，智能体没有执行任何业务操作。"
                    "请检查网络和账户状态，或重新输入 API Key 后再试。",
                    None,
                )
            intent = decision["intent"]

        if intent == "cancel":
            self.session.pending_action = None
            return "当前待执行操作已取消。请告诉我下一步需要检查什么。", None
        if intent == "confirm":
            return self._execute_pending()
        if intent == "list_files":
            return self._describe_files(), None
        if intent == "knowledge":
            return self._answer_knowledge(user_message), None
        if intent == "config_ready":
            return self._handle_config_ready(), None
        if intent == "create_config":
            return self._prepare_config(), None
        if intent == "return_offset":
            return self._prepare_return_check(), None
        if intent == "sales_medical":
            return self._prepare_sales_compare(), None
        if intent == "medical_sales_detail":
            return self._prepare_medical_sales_detail_screen(), None
        if intent == "prescription_medical":
            return self._prepare_prescription_compare(), None
        return self._answer_general(user_message), None

    def _answer_knowledge(self, question: str) -> str:
        """知识问答只发送说明文档，不发送患者、交易或处方明细。"""
        context = self.knowledge_base.context(question)
        prompt = (
            f"最近十轮对话：\n{self.session.history_text()}\n\n"
            f"用户问题：{question}\n\n本地知识：\n{context}"
        )
        try:
            response = self.model.invoke(
                [
                    SystemMessage(content=KNOWLEDGE_ANSWER_PROMPT),
                    HumanMessage(content=prompt),
                ]
            )
            return str(response.content)
        except Exception:
            # 明确标记离线回退，避免用户误以为错误密钥已经通过验证。
            return (
                "DeepSeek 本次调用失败，下面仅显示本地离线说明：\n\n"
                f"{context}\n\n下一步：请检查网络、API Key 和账户状态后重试。"
            )

    def _answer_general(self, user_message: str) -> str:
        """普通闲聊简短回应，随后结合当前材料自然引导回业务操作。"""
        guidance = self._contextual_guidance()
        try:
            response = self.model.invoke(
                [
                    SystemMessage(content=GENERAL_CHAT_PROMPT),
                    HumanMessage(
                        content=(
                            f"最近十轮对话：\n{self.session.history_text()}\n\n"
                            f"用户说：{user_message}\n当前建议：{guidance}"
                        )
                    ),
                ]
            )
            return str(response.content)
        except Exception:
            return f"我明白了。{guidance}"

    def _contextual_guidance(self) -> str:
        inventory = discover_files(self.workspace)
        if (
            inventory.sales_medical_results
            and inventory.medical_sales_detail_results
            and inventory.prescription_medical_results
        ):
            return "药品串换疑点、医保销售明细和处方医保筛查结果均已生成，建议查看结果并进行人工复核。"
        if not inventory.configs:
            return "当前还没有列名配置，建议先说“生成列名配置”。"
        if self.session.return_output and self.session.return_output.exists():
            if inventory.medical:
                return "冲销结果和医保端文件已经具备，建议下一步进行销售医保药品串换疑点筛查。"
            return "退货冲销检查已完成。建议下一步把医保端文件复制到工作目录，或先查看当前文件。"
        if inventory.sales:
            return "当前已找到销售端文件和列名配置，建议下一步执行退货冲销检查。"
        if inventory.prescription and inventory.medical and inventory.catalog:
            return "处方端、医保端和处方药目录已经具备，可以进行处方医保综合比对。"
        return "我可以根据工作目录中的文件继续协助；您也可以问我还缺少哪些材料。"

    def _next_input_suggestion(self) -> str:
        """结合短期记忆、待执行操作和当前文件，给用户一条可直接输入的下一步指令。"""
        if self.session.pending_action:
            return "可直接输入：“确认”执行当前操作；如果不想执行，输入“取消”。"

        inventory = discover_files(self.workspace)
        history = self.session.history_text()
        has_config = bool(inventory.configs)
        has_sales = bool(inventory.sales)
        has_medical = bool(inventory.medical)
        has_prescription = bool(inventory.prescription)
        has_catalog = bool(inventory.catalog)
        has_sales_result = bool(inventory.sales_medical_results)
        has_detail_result = bool(inventory.medical_sales_detail_results)
        has_prescription_result = bool(inventory.prescription_medical_results)
        has_return_output = bool(
            self.session.return_output is not None and self.session.return_output.exists()
        )

        if has_sales_result and has_detail_result and has_prescription_result:
            return "可直接输入：“查看当前文件”。"

        if not has_config:
            return "可直接输入：“生成列名配置”。"

        config_ready_in_history = any(
            word in history
            for word in ("列名配置修改好了", "列名配置改好了", "配置修改好了", "配置改好了", "直接使用")
        )

        if has_return_output and has_medical and not has_sales_result:
            return "可直接输入：“进行销售医保药品串换疑点筛查”。"
        if self.session.last_operation == "return_offset":
            return "可直接输入：“查看当前文件”。"
        if self.session.last_operation == "config_ready" and has_sales and has_config:
            return "可直接输入：“执行退货冲销检查”。"
        if config_ready_in_history and has_sales:
            return "可直接输入：“执行退货冲销检查”。"
        if self.session.last_operation == "create_config":
            return "可直接输入：“我的列名配置修改好了”。"
        if self.session.last_operation == "sales_medical" or has_sales_result:
            if not has_detail_result and has_sales and has_medical and has_config:
                return "可直接输入：“进行医保销售明细筛查”。"
            if (
                not has_prescription_result
                and has_prescription
                and has_medical
                and has_catalog
                and has_config
            ):
                return "可直接输入：“进行处方医保比对”。"
            return "可直接输入：“查看当前文件”。"
        if self.session.last_operation == "medical_sales_detail" or has_detail_result:
            if not has_sales_result and has_sales and has_medical and has_config:
                return "可直接输入：“进行销售医保药品串换疑点筛查”。"
            if (
                not has_prescription_result
                and has_prescription
                and has_medical
                and has_catalog
                and has_config
            ):
                return "可直接输入：“进行处方医保比对”。"
            return "可直接输入：“查看当前文件”。"
        if self.session.last_operation == "prescription_medical" or has_prescription_result:
            if not has_sales_result and has_sales and has_medical and has_config:
                return "可直接输入：“进行销售医保药品串换疑点筛查”。"
            return "可直接输入：“查看当前文件”。"
        if has_sales and has_config:
            return "可直接输入：“执行退货冲销检查”。"
        if has_prescription and has_medical and has_catalog and has_config:
            return "可直接输入：“进行处方医保比对”。"
        if has_medical and has_config:
            return "可直接输入：“查看当前文件”。"
        return "可直接输入：“还缺少哪些材料”。"

    def _append_next_input_suggestion(self, reply: str) -> str:
        inventory = discover_files(self.workspace)
        if (
            inventory.sales_medical_results
            and inventory.medical_sales_detail_results
            and inventory.prescription_medical_results
            and "三项筛查均已完成" not in reply
        ):
            reply += "\n\n当前状态：药品串换疑点、医保销售明细和处方医保三项筛查均已完成。"
        suggestion = self._next_input_suggestion()
        if suggestion in reply:
            return reply
        return f"{reply}\n\n下一步可输入：{suggestion.removeprefix('可直接输入：')}"

    def _next_step_for(self, operation: str) -> str:
        """从知识库读取操作完成后的建议，避免业务说明散落在控制代码里。"""
        section_titles = {
            "create_config": "生成列名配置后",
            "return_offset": "完成退货冲销检查后",
            "sales_medical": "完成销售医保药品串换疑点筛查后",
            "medical_sales_detail": "完成医保销售明细筛查后",
            "prescription_medical": "完成处方医保综合比对后",
        }
        title = section_titles.get(operation)
        if not title:
            return ""
        return self.knowledge_base.section(title) or ""

    def _handle_config_ready(self) -> str:
        inventory = discover_files(self.workspace)
        config, error = self._one_file(inventory.configs, "列名配置")
        if error:
            return error
        try:
            load_column_config(config) # type: ignore
        except Exception as exc:
            return f"我找到了配置表，但暂时无法读取：{exc} 请检查配置表结构。"
        self.session.last_operation = "config_ready"
        return f"好的，已经识别到并读取列名配置。{self._contextual_guidance()}"

    def _describe_files(self) -> str:
        inventory = discover_files(self.workspace)
        lines = [f"当前工作目录：`{self.workspace}`", "已发现："]
        for label, paths in (
            ("销售端候选", inventory.sales),
            ("医保端候选", inventory.medical),
            ("处方端候选", inventory.prescription),
            ("处方药目录", inventory.catalog),
            ("列名配置", inventory.configs),
            ("退货冲销结果", inventory.return_results),
            ("销售医保药品串换疑点筛查结果", inventory.sales_medical_results),
            ("医保销售明细筛查结果", inventory.medical_sales_detail_results),
            ("处方医保比对结果", inventory.prescription_medical_results),
        ):
            value = "、".join(path.name for path in paths) or "无"
            lines.append(f"- {label}：{value}")
        format_hint = self._unsupported_format_hint(inventory)
        if format_hint:
            lines.append(f"\n{format_hint}")
        return "\n".join(lines)

    @staticmethod
    def _unsupported_format_hint(inventory) -> str:
        if not inventory.unsupported_spreadsheets:
            return ""
        names = "、".join(path.name for path in inventory.unsupported_spreadsheets)
        return (
            f"另外发现暂不支持的表格：{names}。当前只识别 `.xlsx` 和 `.csv`；"
            "请用 Excel 打开后另存为 `.xlsx`，再重新检查文件。"
        )

    def _with_format_hint(self, message: str, inventory) -> str:
        hint = self._unsupported_format_hint(inventory)
        return f"{message}\n\n{hint}" if hint else message

    @staticmethod
    def _one_file(paths: list[Path], label: str) -> tuple[Path | None, str | None]:
        if not paths:
            return None, f"没有找到{label}，请先把文件复制到工作目录或附加到对话。"
        if len(paths) > 1:
            names = "、".join(path.name for path in paths)
            return None, f"发现多个{label}：{names}。请暂时移走不用的文件后重试。"
        return paths[0], None

    def _prepare_config(self) -> str:
        inventory = discover_files(self.workspace)
        if inventory.configs:
            names = "、".join(path.name for path in inventory.configs)
            return f"已找到列名配置：{names}。回复“直接使用”可继续现有配置；如需修改，请先说明要调整的字段。"
        output = self.workspace / "列名配置.xlsx"
        self.session.pending_action = PendingAction(
            "create_config", {"output_path": output}, "生成列名配置.xlsx"
        )
        return "当前目录没有列名配置。我可以先生成配置模板。回复“确认”开始生成。"

    def _prepare_return_check(self) -> str:
        inventory = discover_files(self.workspace)
        sales, error = self._one_file(inventory.sales, "销售端 Excel")
        if error:
            return self._with_format_hint(error, inventory)
        config, error = self._one_file(inventory.configs, "列名配置")
        if error:
            return error
        pharmacy = infer_pharmacy_name(sales) # type: ignore
        output = unique_output_path(self.workspace, pharmacy, "退货冲销检查", ".xlsx")
        self.session.pending_action = PendingAction(
            "return_offset",
            {"input_path": sales, "output_path": output, "config_path": config}, # type: ignore
            f"使用 {sales.name} 执行退货冲销检查", # type: ignore
        )
        return f"准备执行：{self.session.pending_action.summary}。回复“确认”开始。"

    def _prepare_sales_compare(self) -> str:
        inventory = discover_files(self.workspace)
        using_return_result = bool(
            self.session.return_output is not None and self.session.return_output.exists()
        )
        if using_return_result:
            sales_path = self.session.return_output
        else:
            sales_path, error = self._one_file(inventory.sales, "销售端 Excel")
            if error:
                return self._with_format_hint(error, inventory)
        medical, error = self._one_file(inventory.medical, "医保端 CSV")
        if error:
            return self._with_format_hint(error, inventory)
        config, error = self._one_file(inventory.configs, "列名配置")
        if error:
            return error
        pharmacy = infer_pharmacy_name(sales_path) # pyright: ignore[reportArgumentType]
        output = unique_output_path(
            self.workspace,
            pharmacy,
            "销售医保药品串换疑点筛查",
            ".xlsx",
        )
        self.session.pending_action = PendingAction(
            "sales_medical",
            {
                "sales_path": sales_path,
                "medical_path": medical,
                "output_path": output,
                "config_path": config,
            }, # type: ignore
            f"使用 {sales_path.name} 与 {medical.name} 进行销售医保药品串换疑点筛查", # type: ignore
        )
        if not using_return_result and "skip_return_offset" not in self.session.warnings_shown:
            self.session.warnings_shown.add("skip_return_offset")
            return (
                "当前销售文件还没有在本次会话中完成退货冲销检查。先筛除冲销记录通常能让比对更准确。"
                "如果您仍希望直接比对，请回复“继续执行”；如果先做冲销，请说“执行冲销检查”。"
            )
        if using_return_result:
            return (
                f"准备执行：{self.session.pending_action.summary}。"
                "开始前请确认您已手工删除“冲销编号”不为空的行，只保留未参与冲销的数据。"
                "确认已完成后，回复“确认”开始。"
            )
        return f"准备执行：{self.session.pending_action.summary}。回复“确认”开始。"

    def _prepare_medical_sales_detail_screen(self) -> str:
        inventory = discover_files(self.workspace)
        sales, error = self._one_file(inventory.sales, "销售端 Excel")
        if error:
            return self._with_format_hint(error, inventory)
        medical, error = self._one_file(inventory.medical, "医保端 CSV")
        if error:
            return self._with_format_hint(error, inventory)
        config, error = self._one_file(inventory.configs, "列名配置")
        if error:
            return error
        pharmacy = infer_pharmacy_name(medical, sales) # type: ignore
        output = unique_output_path(
            self.workspace,
            pharmacy,
            "医保销售明细筛查",
            ".csv",
        )
        self.session.pending_action = PendingAction(
            "medical_sales_detail",
            {
                "sales_path": sales,
                "medical_path": medical,
                "output_path": output,
                "config_path": config,
            }, # type: ignore
            f"使用 {medical.name} 与 {sales.name} 进行医保销售明细筛查", # type: ignore
        )
        return (
            f"准备执行：{self.session.pending_action.summary}。"
            "程序会先按同名且时间误差不超过 1 分钟的数据分组，再逐组匹配。"
            "回复“确认”开始。"
        )

    def _prepare_prescription_compare(self) -> str:
        inventory = discover_files(self.workspace)
        prescription, error = self._one_file(inventory.prescription, "处方端 Excel")
        if error:
            return self._with_format_hint(error, inventory)
        medical, error = self._one_file(inventory.medical, "医保端 CSV")
        if error:
            return self._with_format_hint(error, inventory)
        catalog, error = self._one_file(inventory.catalog, "处方药目录")
        if error:
            return self._with_format_hint(error, inventory)
        config, error = self._one_file(inventory.configs, "列名配置")
        if error:
            return error
        pharmacy = infer_pharmacy_name(medical, prescription) # type: ignore
        output = unique_output_path(self.workspace, pharmacy, "医保处方比对", ".csv")
        self.session.pending_action = PendingAction(
            "prescription_medical",
            {
                "prescription_path": prescription,
                "medical_path": medical,
                "catalog_path": catalog,
                "output_path": output,
                "config_path": config,
            }, # type: ignore
            "执行处方医保匹配并继续完成处方药目录判断",
        )
        return f"准备执行：{self.session.pending_action.summary}。回复“确认”开始。"

    def _execute_pending(self) -> tuple[str, ToolResult | None]:
        action = self.session.pending_action
        if action is None:
            return f"目前没有需要确认的操作。{self._contextual_guidance()}", None
        self.session.pending_action = None
        if action.name == "create_config":
            result = create_config(**action.arguments)
        elif action.name == "return_offset":
            result = check_returns(**action.arguments)
            if result.success:
                self.session.return_output = result.output_files[0]
        elif action.name == "sales_medical":
            result = compare_sales(**action.arguments)
        elif action.name == "medical_sales_detail":
            result = screen_medical_sales_details(**action.arguments)
        elif action.name == "prescription_medical":
            result = compare_prescriptions(**action.arguments)
        else:
            return "无法识别待执行操作，请重新发起任务。", None

        details = "、".join(f"{key}：{value}" for key, value in result.statistics.items())
        reply = result.message
        if details:
            reply += f"\n\n结果统计：{details}。"
        if result.output_files:
            reply += f"\n\n结果文件：`{result.output_files[0]}`"
        if result.warnings:
            reply += "\n\n建议：" + "；".join(result.warnings)
        if result.success:
            self.session.last_operation = action.name
            next_step = self._next_step_for(action.name)
            if next_step:
                reply += f"\n\n下一步建议：{next_step}"
        return reply, result
