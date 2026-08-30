"""Local explainable ranking and explicitly audited AI briefs for candidates."""
import hashlib
import json
import re
from datetime import date, datetime, timezone
from typing import Any

from config import get as config_get
from processors.ai_provider import AIResponse
from processors.candidate_brief import (
    PROCESSOR_NAME, PROCESSOR_VERSION, PROMPT_VERSION, CandidateBriefProvider,
    validate_result,
)
from services.ai_errors import safe_provider_error
from storage import candidate_ai_runs as run_repository
from storage import candidates as candidate_repository
from storage.workspace import get_active_connection


MIN_BRIEF_CANDIDATES = 2
MAX_BRIEF_CANDIDATES = 10
MAX_RANK_CANDIDATES = 20
TITLE_LIMIT = 300
ABSTRACT_LIMIT = 2_000
INPUT_SCOPE = [
    f"title:{TITLE_LIMIT}", "doi", "authors", "container_title", "publication_date",
    f"best_available_abstract:{ABSTRACT_LIMIT}", "deterministic_score_reasons",
]


def _selection(conn, candidate_ids: list[int], *, minimum: int, maximum: int) -> list[dict[str, Any]]:
    if not minimum <= len(candidate_ids) <= maximum:
        raise ValueError(f"候选数量必须在 {minimum}–{maximum} 之间")
    if len(set(candidate_ids)) != len(candidate_ids) or any(
        isinstance(value, bool) or not isinstance(value, int) or value <= 0
        for value in candidate_ids
    ):
        raise ValueError("候选 ID 必须是互不重复的正整数")
    selected = []
    for candidate_id in candidate_ids:
        candidate = candidate_repository.get_candidate(conn, candidate_id)
        if candidate is None or candidate["status"] != "pending":
            raise ValueError(f"候选 #{candidate_id} 不存在或已完成审核")
        selected.append(candidate)
    return selected


def _best_abstract(candidate: dict[str, Any]) -> str:
    if candidate.get("summary"):
        return candidate["summary"][:ABSTRACT_LIMIT]
    for kind in ("openalex", "arxiv_version", "semantic_scholar"):
        for record in candidate.get("source_records", []):
            abstract = record.get("facts", {}).get("abstract")
            if record.get("source_kind") == kind and record.get("status") == "succeeded" and abstract:
                return str(abstract)[:ABSTRACT_LIMIT]
    return ""


def _publication_date(candidate: dict[str, Any]) -> date | None:
    facts = candidate.get("source_facts", {})
    for key in ("published_online", "published", "published_print", "indexed", "published_at"):
        value = str(facts.get(key) or "")[:10]
        try:
            return date.fromisoformat(value)
        except ValueError:
            continue
    return None


def _code_points(candidate: dict[str, Any]) -> tuple[int, str | None]:
    for record in candidate.get("source_records", []):
        if record.get("source_kind") != "github_code" or record.get("status") != "succeeded":
            continue
        levels = {repo.get("level") for repo in record.get("facts", {}).get("repositories", [])}
        if "paper_declared" in levels:
            return 15, "来源元数据声明了源码仓库 +15"
        if "strong_identifier" in levels:
            return 12, "仓库 README 命中 DOI/arXiv 强身份 +12"
        if "implementation_candidate" in levels:
            return 6, "发现标题/作者匹配的实现候选 +6"
    return 0, None


def _rank_one(
    candidate: dict[str, Any], *, focus: str, preferred_journal: str, today: date,
) -> dict[str, Any]:
    score = 0
    reasons = []
    title = (candidate.get("title") or "").casefold()
    terms = [term for term in re.findall(r"[\w-]+", focus.casefold()) if len(term) > 1][:12]
    if focus.strip() and focus.casefold().strip() in title:
        score += 45
        reasons.append("标题包含完整关注词 +45")
    elif terms:
        matched = sum(term in title for term in terms)
        points = round(40 * matched / len(terms))
        if points:
            score += points
            reasons.append(f"标题命中 {matched}/{len(terms)} 个关注词 +{points}")
    published = _publication_date(candidate)
    if published and published <= today:
        age = (today - published).days
        points = 20 if age <= 30 else 12 if age <= 180 else 6 if age <= 365 else 0
        if points:
            score += points
            reasons.append(f"日期距今约 {age} 天 +{points}")
    container = str(candidate.get("source_facts", {}).get("container_title") or "")
    if preferred_journal.strip() and preferred_journal.casefold().strip() in container.casefold():
        score += 10
        reasons.append("命中指定期刊/会议 +10")
    if not (candidate.get("source_facts", {}).get("existing_candidate_id") or
            candidate.get("source_facts", {}).get("existing_item_id")):
        score += 15
        reasons.append("本工作区新发现 +15")
    abstract = _best_abstract(candidate)
    if abstract:
        score += 10
        reasons.append("有可追溯摘要 +10")
    code_score, code_reason = _code_points(candidate)
    score += code_score
    if code_reason:
        reasons.append(code_reason)
    return {"candidate_id": candidate["id"], "score": score, "reasons": reasons}


def rank_candidates(
    candidate_ids: list[int], *, focus: str = "", preferred_journal: str = "",
    today: date | None = None,
) -> list[dict[str, Any]]:
    if len(focus) > 200 or len(preferred_journal) > 200:
        raise ValueError("排序关注词和期刊名称不能超过 200 字符")
    conn = get_active_connection()
    try:
        selected = _selection(conn, candidate_ids, minimum=1, maximum=MAX_RANK_CANDIDATES)
    finally:
        conn.close()
    ranked = [
        _rank_one(candidate, focus=focus, preferred_journal=preferred_journal,
                  today=today or datetime.now(timezone.utc).date())
        for candidate in selected
    ]
    return sorted(ranked, key=lambda value: (-value["score"], value["candidate_id"]))


def list_candidate_briefs() -> list[dict[str, Any]]:
    conn = get_active_connection()
    try:
        return run_repository.list_runs(conn)
    finally:
        conn.close()


async def create_candidate_brief(
    candidate_ids: list[int], *, focus: str = "", preferred_journal: str = "",
    provider_client: Any | None = None,
) -> dict[str, Any]:
    provider = config_get("ai", "api_type") or "openai"
    model = (config_get("ai", "model") or "").strip()
    conn = get_active_connection()
    try:
        selected = _selection(
            conn, candidate_ids, minimum=MIN_BRIEF_CANDIDATES,
            maximum=MAX_BRIEF_CANDIDATES,
        )
        ranking = {row["candidate_id"]: row for row in [
            _rank_one(candidate, focus=focus, preferred_journal=preferred_journal,
                      today=datetime.now(timezone.utc).date()) for candidate in selected
        ]}
        selected_input = [{
            "candidate_id": candidate["id"],
            "title": (candidate.get("title") or "")[:TITLE_LIMIT],
            "doi": candidate.get("source_facts", {}).get("doi"),
            "authors": candidate.get("source_facts", {}).get("authors", [])[:20],
            "container_title": candidate.get("source_facts", {}).get("container_title"),
            "publication_date": (_publication_date(candidate) or "").isoformat()
            if _publication_date(candidate) else None,
            "abstract": _best_abstract(candidate),
            "deterministic_score": ranking[candidate["id"]]["score"],
            "score_reasons": ranking[candidate["id"]]["reasons"],
        } for candidate in selected]
        digest = hashlib.sha256(json.dumps(
            {"prompt_version": PROMPT_VERSION, "input_scope": INPUT_SCOPE, "input": selected_input},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()
        run = run_repository.create_run(
            conn, candidate_ids=candidate_ids, input_scope=INPUT_SCOPE, input_hash=digest,
            processor=PROCESSOR_NAME, processor_version=PROCESSOR_VERSION,
            prompt_version=PROMPT_VERSION, provider=provider, model=model,
        )
        api_key = (config_get("ai", "api_key") or "").strip()
        if not model or (provider != "ollama" and not api_key):
            return run_repository.complete_run(
                conn, run["id"], error_message="尚未配置可用模型，请先到设置页配置 API Key 和模型"
            )
        response = None
        try:
            response = await (provider_client or CandidateBriefProvider()).review(selected_input)
            if not isinstance(response, AIResponse):
                raise RuntimeError("模型未返回可审计响应")
        except Exception as exc:
            return run_repository.complete_run(
                conn, run["id"], error_message=safe_provider_error(exc, "候选简报失败，请稍后重试")
            )
        metadata = {"provider_model": response.provider_model, "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens, "duration_ms": response.duration_ms,
                    "request_id": response.request_id}
        try:
            result = validate_result(response.content, candidate_ids)
            return run_repository.complete_run(conn, run["id"], result=result, provider_metadata=metadata)
        except Exception as exc:
            message = str(exc)[:1_000] if isinstance(exc, ValueError) else "候选简报结果处理失败"
            return run_repository.complete_run(
                conn, run["id"], error_message=message, provider_metadata=metadata
            )
    finally:
        conn.close()
