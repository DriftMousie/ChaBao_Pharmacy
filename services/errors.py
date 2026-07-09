from __future__ import annotations

from pathlib import Path

from models.results import UserFacingError


def explain_exception(exc: Exception, stage: str) -> UserFacingError:
    """将底层异常转换成用户能理解的错误，不把 traceback 暴露到对话中。"""
    message = str(exc)
    if isinstance(exc, FileNotFoundError):
        return UserFacingError(
            error_code="FILE_NOT_FOUND",
            stage=stage,
            technical_message=message,
            user_message="没有找到需要的文件。",
            suggestions=["请把文件复制到工作目录，或在对话中附加文件。"],
        )
    if isinstance(exc, PermissionError):
        return UserFacingError(
            error_code="OUTPUT_WRITE_ERROR",
            stage=stage,
            technical_message=message,
            user_message="文件无法读取或写入，可能正在被 Excel 占用。",
            suggestions=["请关闭相关 Excel 文件后重试。"],
        )
    if isinstance(exc, ValueError) and "缺少必要列" in message:
        return UserFacingError(
            error_code="MISSING_REQUIRED_COLUMN",
            stage=stage,
            technical_message=message,
            user_message=message,
            suggestions=["请检查列名配置，或让智能体重新读取表头并修改配置。"],
        )
    return UserFacingError(
        error_code="UNEXPECTED_ERROR",
        stage=stage,
        technical_message=f"{type(exc).__name__}: {message}",
        user_message="执行过程中出现了未预期的问题。",
        suggestions=["请根据技术详情检查输入文件；如果问题持续，请保留日志。"],
    )

