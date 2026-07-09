from __future__ import annotations

from pathlib import Path

from models.results import ToolResult
from pharmacy_analysis import (
    create_column_config_template,
    run_prescription_medical_compare,
    run_return_offset_check,
    run_sales_medical_compare,
)
from services.errors import explain_exception


def create_config(output_path: Path) -> ToolResult:
    try:
        path = create_column_config_template(output_path)
        return ToolResult(True, "create_config", "列名配置表已生成。", output_files=[path])
    except Exception as exc:
        error = explain_exception(exc, "生成列名配置")
        return ToolResult(False, "create_config", error.user_message, warnings=error.suggestions)


def check_returns(input_path: Path, output_path: Path, config_path: Path) -> ToolResult:
    try:
        result = run_return_offset_check(input_path, output_path, config_path)
        return ToolResult(
            True,
            "return_offset",
            "退货冲销检查完成。",
            statistics={
                "总行数": result.total_rows,
                "冲销对数": result.matched_pairs,
                "未匹配负数行": result.unmatched_negative_rows,
            },
            output_files=[result.output_path],
        )
    except Exception as exc:
        error = explain_exception(exc, "退货冲销检查")
        return ToolResult(False, "return_offset", error.user_message, warnings=error.suggestions)


def compare_sales(
    sales_path: Path,
    medical_path: Path,
    output_path: Path,
    config_path: Path,
) -> ToolResult:
    try:
        result = run_sales_medical_compare(sales_path, medical_path, output_path, config_path)
        return ToolResult(
            True,
            "sales_medical",
            "销售端与医保端比对完成。",
            statistics={
                "医保编号数": result.medical_bill_count,
                "匹配编号数": result.matched_bill_count,
                "不完全匹配编号数": result.incomplete_matched_bill_count,
                "未匹配编号数": result.unmatched_bill_count,
            },
            output_files=[result.output_path],
        )
    except Exception as exc:
        error = explain_exception(exc, "销售医保比对")
        return ToolResult(False, "sales_medical", error.user_message, warnings=error.suggestions)


def compare_prescriptions(
    prescription_path: Path,
    medical_path: Path,
    catalog_path: Path,
    output_path: Path,
    config_path: Path,
) -> ToolResult:
    try:
        result = run_prescription_medical_compare(
            prescription_path,
            medical_path,
            catalog_path,
            output_path,
            config_path,
        )
        return ToolResult(
            True,
            "prescription_medical",
            "处方端医保端综合比对完成。",
            statistics={
                "医保明细数": result.total_rows,
                "正常开方": result.normal_rows,
                "先药后方": result.after_medicine_rows,
                "无处方": result.missing_rows,
                "处方药": result.prescription_drug_rows,
                "非处方药": result.non_prescription_drug_rows,
            },
            output_files=[result.output_path],
        )
    except Exception as exc:
        error = explain_exception(exc, "处方医保综合比对")
        return ToolResult(False, "prescription_medical", error.user_message, warnings=error.suggestions)

