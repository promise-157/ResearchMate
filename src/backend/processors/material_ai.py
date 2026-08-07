"""Strict AI adapter for auditable generic-material analysis."""
import json
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from processors.llm_analyzer import LLMAnalyzer


PROCESSOR_NAME = "material_ai"
PROCESSOR_VERSION = "1"
PROMPT_VERSIONS = {
    "classify": "material-classify-v1",
    "extract": "material-extract-v1",
    "compare": "material-compare-v1",
}


class ClassificationSuggestion(BaseModel):
    suggested_type: str
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1, max_length=500)


class ExtractionSuggestion(BaseModel):
    summary: str = Field(min_length=1, max_length=1000)
    tags: list[str] = Field(max_length=20)
    fields: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class ComparisonSuggestion(BaseModel):
    summary: str = Field(min_length=1, max_length=2000)
    common_themes: list[str] = Field(max_length=20)
    differences: list[str] = Field(max_length=30)
    item_insights: dict[str, str] = Field(default_factory=dict)


def _json_object(text: str) -> dict[str, Any]:
    candidate = text.strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", candidate)
    if fenced:
        candidate = fenced.group(1).strip()
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError("模型返回的不是有效 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("模型返回必须是 JSON 对象")
    return value


def validate_result(analysis_type: str, raw_text: str) -> dict[str, Any]:
    value = _json_object(raw_text)
    try:
        if analysis_type == "classify":
            result = ClassificationSuggestion.model_validate(value)
            if result.suggested_type not in {"general", "paper", "job", "debug"}:
                raise ValueError("模型返回了未知资料类型")
        elif analysis_type == "extract":
            result = ExtractionSuggestion.model_validate(value)
        elif analysis_type == "compare":
            result = ComparisonSuggestion.model_validate(value)
        else:
            raise ValueError("未知分析类型")
    except ValidationError as exc:
        raise ValueError("模型返回未通过结构校验") from exc
    return result.model_dump()


def build_prompt(analysis_type: str, selected_input: dict[str, Any]) -> str:
    input_json = json.dumps(selected_input, ensure_ascii=False, sort_keys=True)
    if analysis_type == "classify":
        instruction = (
            '返回且只返回 JSON：{"suggested_type":"general|paper|job|debug",'
            '"confidence":0到1,"reason":"简短依据"}。'
        )
    elif analysis_type == "extract":
        instruction = (
            '返回且只返回 JSON：{"summary":"摘要","tags":["标签"],'
            '"fields":{"字段名":"标量值"}}。fields 只放输入中有明确证据的结构化字段。'
        )
    elif analysis_type == "compare":
        instruction = (
            '返回且只返回 JSON：{"summary":"总体归纳","common_themes":["共同点"],'
            '"differences":["差异"],"item_insights":{"资料ID":"单条洞察"}}。'
        )
    else:
        raise ValueError("未知分析类型")
    return f"你在分析一条用户明确选中的资料。不要补造事实。{instruction}\n输入：{input_json}"


class MaterialAIProvider:
    """Backend-only adapter; tests inject a fake provider instead."""

    async def analyze(self, analysis_type: str, selected_input: dict[str, Any]) -> str:
        raw = await LLMAnalyzer()._call_llm_raw(build_prompt(analysis_type, selected_input))
        if not raw:
            raise RuntimeError("模型调用失败；请检查模型名称、API Base URL 和后端日志")
        return raw
