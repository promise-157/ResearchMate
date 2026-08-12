"""Audited, workspace-local analysis of explicitly selected cart papers."""
import hashlib
import json
from typing import Any

from config import get as config_get
from processors.ai_provider import AIResponse
from processors.paper_ai import (
    PROCESSOR_NAME,
    PROCESSOR_VERSION,
    PROMPT_VERSION,
    PaperAIProvider,
    validate_result,
)
from storage import paper_ai_runs as run_repository
from storage import papers as paper_repository
from storage.workspace import get_active_connection
from services.ai_errors import safe_provider_error


MAX_PAPERS = 20
TITLE_LIMIT = 300
ABSTRACT_LIMIT = 3_000
INPUT_SCOPE = ["title", "abstract"]


def list_cart_papers() -> list[dict[str, Any]]:
    conn = get_active_connection()
    try:
        papers = paper_repository.list_cart(conn)
        for paper in papers:
            paper["analysis_runs"] = run_repository.list_runs_for_paper(
                conn, paper["id"]
            )
        return papers
    finally:
        conn.close()


def list_cart_paper_ids() -> list[int]:
    conn = get_active_connection()
    try:
        return paper_repository.list_cart_ids(conn)
    finally:
        conn.close()


def _validate_selection(conn, paper_ids: list[int]) -> list[dict[str, Any]]:
    if not 1 <= len(paper_ids) <= MAX_PAPERS:
        raise ValueError(f"请选择 1–{MAX_PAPERS} 篇购物车论文")
    if len(set(paper_ids)) != len(paper_ids):
        raise ValueError("论文清单不能包含重复项")
    if any(isinstance(paper_id, bool) or paper_id <= 0 for paper_id in paper_ids):
        raise ValueError("论文 ID 必须是正整数")

    papers = paper_repository.get_cart_selection(conn, paper_ids)
    if len(papers) != len(paper_ids):
        raise ValueError("部分论文不存在或已不在当前工作区购物车，请刷新后重试")
    return papers


def list_cart_export_rows() -> list[dict[str, Any]]:
    conn = get_active_connection()
    try:
        return paper_repository.list_cart_export_rows(conn)
    finally:
        conn.close()


def _selected_input(paper: dict[str, Any]) -> dict[str, str]:
    return {
        "title": (paper.get("title") or "")[:TITLE_LIMIT],
        "abstract": (paper.get("abstract") or "")[:ABSTRACT_LIMIT],
    }


def _input_hash(selected_input: dict[str, str]) -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "run_kind": "paper_analysis",
                "prompt_version": PROMPT_VERSION,
                "input": selected_input,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _metadata(response: AIResponse | None) -> dict[str, Any] | None:
    if response is None:
        return None
    return {
        "provider_model": response.provider_model,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "duration_ms": response.duration_ms,
        "request_id": response.request_id,
    }


async def analyze_cart_papers(
    paper_ids: list[int], *, provider_client: Any | None = None
) -> dict[str, Any]:
    provider = config_get("ai", "api_type") or "openai"
    model = (config_get("ai", "model") or "").strip()
    conn = get_active_connection()
    try:
        papers = _validate_selection(conn, paper_ids)
        runs = []
        for paper in papers:
            selected_input = _selected_input(paper)
            run = run_repository.create_run(
                conn,
                paper_id=paper["id"],
                paper_ids=[paper["id"]],
                run_kind="paper_analysis",
                input_scope=INPUT_SCOPE,
                input_hash=_input_hash(selected_input),
                processor=PROCESSOR_NAME,
                processor_version=PROCESSOR_VERSION,
                prompt_version=PROMPT_VERSION,
                provider=provider,
                model=model,
            )
            response = None
            api_key = (config_get("ai", "api_key") or "").strip()
            if not model or (provider != "ollama" and not api_key):
                completed = run_repository.complete_run(
                    conn,
                    run["id"],
                    error_message="尚未配置可用模型，请先到设置页配置 API Key 和模型",
                )
                runs.append(completed)
                continue
            try:
                provider_result = await (provider_client or PaperAIProvider()).analyze(
                    selected_input
                )
                if not isinstance(provider_result, AIResponse):
                    raise RuntimeError("模型未返回可审计响应")
                response = provider_result
            except Exception as exc:
                completed = run_repository.complete_run(
                    conn,
                    run["id"],
                    error_message=safe_provider_error(
                        exc, "论文分析失败，请稍后重试"
                    ),
                )
                runs.append(completed)
                continue
            try:
                result = validate_result(response.content)
                completed = run_repository.complete_run(
                    conn,
                    run["id"],
                    result=result,
                    provider_metadata=_metadata(response),
                )
            except Exception as exc:
                completed = run_repository.complete_run(
                    conn,
                    run["id"],
                    error_message=(
                        str(exc).strip()[:1_000]
                        if isinstance(exc, ValueError)
                        else "论文分析结果处理失败，请稍后重试"
                    ),
                    provider_metadata=_metadata(response),
                )
            runs.append(completed)

        succeeded = sum(run["status"] == "succeeded" for run in runs)
        failed = len(runs) - succeeded
        overall_status = (
            "succeeded" if failed == 0 else "failed" if succeeded == 0 else "partial"
        )
        message = {
            "succeeded": f"已完成 {succeeded}/{len(runs)} 篇论文分析",
            "partial": f"部分完成：成功 {succeeded}/{len(runs)} 篇，请查看逐篇失败原因",
            "failed": "全部论文分析失败，请查看逐篇失败原因",
        }[overall_status]
        return {
            "ok": failed == 0,
            "overall_status": overall_status,
            "requested": len(runs),
            "succeeded": succeeded,
            "failed": failed,
            "analyzed": succeeded,
            "runs": runs,
            "message": message,
        }
    finally:
        conn.close()
