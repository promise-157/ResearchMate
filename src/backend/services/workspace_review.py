"""Audited review of 2-20 explicitly selected workspace papers."""
import hashlib
import json
from typing import Any

from config import get as config_get
from processors.ai_provider import AIResponse
from processors.workspace_review import (
    PROCESSOR_NAME,
    PROCESSOR_VERSION,
    PROMPT_VERSION,
    WorkspaceReviewProvider,
    validate_result,
)
from services.ai_errors import safe_provider_error
from storage import paper_ai_runs as run_repository
from storage import papers as paper_repository
from storage.workspace import get_active_connection


MIN_PAPERS = 2
MAX_PAPERS = 20
TITLE_LIMIT = 300
ABSTRACT_LIMIT = 2_000
INPUT_SCOPE = [f"title:{TITLE_LIMIT}", f"abstract:{ABSTRACT_LIMIT}"]


def _validate_selection(conn, paper_ids: list[int]) -> list[dict[str, Any]]:
    if not MIN_PAPERS <= len(paper_ids) <= MAX_PAPERS:
        raise ValueError(f"请选择 {MIN_PAPERS}–{MAX_PAPERS} 篇论文生成综述")
    if len(set(paper_ids)) != len(paper_ids):
        raise ValueError("论文清单不能包含重复项")
    if any(
        isinstance(paper_id, bool)
        or not isinstance(paper_id, int)
        or paper_id <= 0
        for paper_id in paper_ids
    ):
        raise ValueError("论文 ID 必须是正整数")
    papers = paper_repository.get_selection(conn, paper_ids)
    if len(papers) != len(paper_ids):
        raise ValueError("部分论文不存在于当前工作区，请刷新后重新选择")
    return papers


def _selected_input(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "paper_id": paper["id"],
            "title": (paper.get("title") or "")[:TITLE_LIMIT],
            "abstract": (paper.get("abstract") or "")[:ABSTRACT_LIMIT],
        }
        for paper in papers
    ]


def _input_hash(selected_input: list[dict[str, Any]]) -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "run_kind": "workspace_review",
                "prompt_version": PROMPT_VERSION,
                "input_scope": INPUT_SCOPE,
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


def list_review_history() -> dict[str, Any]:
    conn = get_active_connection()
    try:
        return {
            "runs": run_repository.list_runs(
                conn, run_kind="workspace_review", limit=50
            ),
            "legacy_reviews": run_repository.list_legacy_workspace_reviews(
                conn, limit=20
            ),
            "limits": {
                "min_papers": MIN_PAPERS,
                "max_papers": MAX_PAPERS,
                "fields": [
                    {"name": "title", "max_chars_per_paper": TITLE_LIMIT},
                    {"name": "abstract", "max_chars_per_paper": ABSTRACT_LIMIT},
                ],
            },
        }
    finally:
        conn.close()


async def create_review(
    paper_ids: list[int], *, provider_client: Any | None = None
) -> dict[str, Any]:
    provider = config_get("ai", "api_type") or "openai"
    model = (config_get("ai", "model") or "").strip()
    conn = get_active_connection()
    try:
        papers = _validate_selection(conn, paper_ids)
        selected_input = _selected_input(papers)
        run = run_repository.create_run(
            conn,
            paper_id=None,
            paper_ids=paper_ids,
            run_kind="workspace_review",
            input_scope=INPUT_SCOPE,
            input_hash=_input_hash(selected_input),
            processor=PROCESSOR_NAME,
            processor_version=PROCESSOR_VERSION,
            prompt_version=PROMPT_VERSION,
            provider=provider,
            model=model,
        )
        api_key = (config_get("ai", "api_key") or "").strip()
        if not model or (provider != "ollama" and not api_key):
            return run_repository.complete_run(
                conn,
                run["id"],
                error_message="尚未配置可用模型，请先到设置页配置 API Key 和模型",
            )

        response = None
        try:
            response = await (
                provider_client or WorkspaceReviewProvider()
            ).review(selected_input)
            if not isinstance(response, AIResponse):
                raise RuntimeError("模型未返回可审计响应")
        except Exception as exc:
            return run_repository.complete_run(
                conn,
                run["id"],
                error_message=safe_provider_error(
                    exc, "工作区综述失败，请稍后重试"
                ),
            )
        try:
            result = validate_result(response.content, paper_ids)
            return run_repository.complete_run(
                conn,
                run["id"],
                result=result,
                provider_metadata=_metadata(response),
            )
        except Exception as exc:
            error_message = (
                str(exc).strip()[:1_000]
                if isinstance(exc, ValueError)
                else "工作区综述结果处理失败，请稍后重试"
            )
            return run_repository.complete_run(
                conn,
                run["id"],
                error_message=error_message,
                provider_metadata=_metadata(response),
            )
    finally:
        conn.close()
