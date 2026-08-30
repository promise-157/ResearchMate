"""Persistent, bounded public-source discovery workflows."""
import asyncio
import hashlib
from datetime import date, datetime, timedelta, timezone
from typing import Any

from crawlers.arxiv_discovery import ArxivDiscoveryCollector
from crawlers.arxiv_version_enrichment import ArxivVersionCollector
from crawlers.crossref_discovery import CrossrefDiscoveryCollector
from crawlers.github_code_evidence import GitHubCodeEvidenceCollector
from crawlers.openalex_enrichment import OpenAlexEnrichmentCollector
from crawlers.semantic_scholar_enrichment import SemanticScholarEnrichmentCollector
from services.materials import normalize_text
from storage import candidates as candidate_repository
from storage import discovery_rules as rule_repository
from storage import items as item_repository
from storage.workspace import get_active_connection


def list_collection_jobs() -> list[dict[str, Any]]:
    conn = get_active_connection()
    try:
        return candidate_repository.list_jobs(conn)
    finally:
        conn.close()


def list_discovery_rules() -> list[dict[str, Any]]:
    conn = get_active_connection()
    try:
        return rule_repository.list_rules(conn)
    finally:
        conn.close()


def save_discovery_rule(name: str, query: dict[str, Any]) -> dict[str, Any]:
    normalized_name = " ".join(name.split())
    if not normalized_name or len(normalized_name) > 100:
        raise ValueError("规则名称必须为 1–100 个字符")
    conn = get_active_connection()
    try:
        return rule_repository.create_rule(
            conn, name=normalized_name, source_kind="crossref_ieee", query=query
        )
    finally:
        conn.close()


def update_discovery_rule(rule_id: int, name: str, query: dict[str, Any]) -> dict[str, Any]:
    normalized_name = " ".join(name.split())
    if not normalized_name or len(normalized_name) > 100:
        raise ValueError("规则名称必须为 1–100 个字符")
    conn = get_active_connection()
    try:
        rule = rule_repository.update_rule(conn, rule_id, name=normalized_name, query=query)
        if rule is None:
            raise ValueError("保存的搜索规则不存在")
        return rule
    finally:
        conn.close()


def delete_discovery_rule(rule_id: int) -> None:
    conn = get_active_connection()
    try:
        if not rule_repository.delete_rule(conn, rule_id):
            raise ValueError("保存的搜索规则不存在")
    finally:
        conn.close()


async def run_discovery_rule(
    rule_id: int, *, collector: Any | None = None, now: datetime | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    conn = get_active_connection()
    try:
        rule = rule_repository.get_rule(conn, rule_id)
    finally:
        conn.close()
    if rule is None:
        raise ValueError("保存的搜索规则不存在")
    if rule["source_kind"] != "crossref_ieee":
        raise ValueError("保存的搜索来源不受支持")
    ran_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    query = _incremental_rule_query(rule, ran_at.date())
    try:
        job, candidates = await discover_crossref(query, collector=collector)
    except Exception as exc:
        conn = get_active_connection()
        try:
            rule_repository.record_run(
                conn, rule_id, ran_at=ran_at.isoformat(), status="failed",
                error=(str(exc).strip()[:1_000] or "搜索失败"),
            )
        finally:
            conn.close()
        raise
    conn = get_active_connection()
    try:
        rule_repository.record_run(
            conn, rule_id, ran_at=ran_at.isoformat(), status="succeeded", job_id=job["id"]
        )
    finally:
        conn.close()
    return job, candidates


def _incremental_rule_query(rule: dict[str, Any], today: date) -> dict[str, Any]:
    query = dict(rule["query"])
    if query.get("intent") == "exact" or not rule.get("last_success_at"):
        return query
    try:
        checkpoint = datetime.fromisoformat(rule["last_success_at"].replace("Z", "+00:00")).date()
        original_from = date.fromisoformat(query["date_from"])
    except (TypeError, ValueError, KeyError):
        return query
    query["date_from"] = max(original_from, checkpoint - timedelta(days=2)).isoformat()
    query["date_to"] = max(today, date.fromisoformat(query["date_from"])).isoformat()
    return query


async def run_all_discovery_rules(
    *, collector_factory: Any | None = None, now: datetime | None = None,
) -> list[dict[str, Any]]:
    rules = list_discovery_rules()
    if len(rules) > 50:
        raise ValueError("一次最多运行 50 条保存规则")
    results = []
    for rule in reversed(rules):
        try:
            collector = collector_factory(rule) if collector_factory else None
            job, candidates = await run_discovery_rule(rule["id"], collector=collector, now=now)
            results.append({
                "rule_id": rule["id"], "status": "succeeded", "job": job,
                "candidate_count": len(candidates),
            })
        except (ValueError, RuntimeError) as exc:
            results.append({"rule_id": rule["id"], "status": "failed", "error": str(exc)})
    return results


async def check_code_evidence(
    candidate_ids: list[int], *, collector: Any | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not 1 <= len(candidate_ids) <= 5:
        raise ValueError("源码检查候选数量必须在 1–5 之间")
    if len(set(candidate_ids)) != len(candidate_ids) or any(value < 1 for value in candidate_ids):
        raise ValueError("源码检查候选 ID 无效或重复")
    conn = get_active_connection()
    job = None
    try:
        selected = []
        for candidate_id in candidate_ids:
            candidate = candidate_repository.get_candidate(conn, candidate_id)
            if candidate is None or candidate["status"] != "pending":
                raise ValueError(f"候选 #{candidate_id} 不存在或已完成审核")
            facts = candidate.get("source_facts", {})
            doi = facts.get("doi")
            arxiv_id = facts.get("arxiv_id")
            if not doi and not arxiv_id:
                raise ValueError(f"候选 #{candidate_id} 缺少 DOI 或 arXiv 身份")
            evidence_texts = [candidate.get("content_text", ""), facts.get("comment", "")]
            linked_arxiv_id = arxiv_id
            for record in candidate.get("source_records", []):
                record_facts = record.get("facts", {})
                evidence_texts.extend([
                    record_facts.get("abstract", ""), record_facts.get("comment", ""),
                ])
                if record["source_kind"] == "arxiv_version" and record["status"] == "succeeded":
                    linked_arxiv_id = record_facts.get("arxiv_id") or linked_arxiv_id
            selected.append({
                "candidate_id": candidate["id"], "title": candidate["title"],
                "doi": doi, "arxiv_id": linked_arxiv_id,
                "authors": facts.get("authors", []), "evidence_texts": evidence_texts,
            })
        job = candidate_repository.create_job(conn, collector="github_code_evidence", query={
            "candidates": [
                {key: paper[key] for key in ("candidate_id", "title", "doi", "arxiv_id")}
                for paper in selected
            ],
            "limits": {"candidate_count": 5, "repositories_per_candidate": 3},
        })
        async with asyncio.timeout(30):
            result = await (collector or GitHubCodeEvidenceCollector()).check(selected)
        fetched_at = datetime.now(timezone.utc).isoformat()
        found_count = 0
        for paper in selected:
            candidate_id = paper["candidate_id"]
            facts = result.records_by_candidate_id.get(candidate_id)
            error = result.errors_by_candidate_id.get(candidate_id)
            if facts is None:
                candidate_repository.create_source_record(conn, {
                    "candidate_id": candidate_id, "job_id": job["id"],
                    "source_kind": "github_code", "status": "failed", "facts": {},
                    "error_message": error or "GitHub 源码检查未返回结果", "fetched_at": fetched_at,
                })
                continue
            if facts.get("repositories"):
                found_count += 1
            candidate_repository.create_source_record(conn, {
                "candidate_id": candidate_id, "job_id": job["id"],
                "source_kind": "github_code", "source_record_id": facts["source_record_id"],
                "status": "succeeded", "facts": facts, "fetched_at": facts["fetched_at"],
            })
        succeeded = len(result.records_by_candidate_id)
        failed = len(selected) - succeeded
        job = candidate_repository.complete_job(
            conn, job["id"], candidate_count=succeeded,
            result={"requested_count": len(selected), "succeeded_count": succeeded,
                    "failed_count": failed, "found_count": found_count,
                    "not_found_count": succeeded - found_count,
                    "partial": succeeded > 0 and failed > 0},
        )
        conn.commit()
        return job, [candidate_repository.get_candidate(conn, paper["candidate_id"])
                     for paper in selected]
    except Exception as exc:
        conn.rollback()
        message = str(exc).strip()[:1_000] or "源码证据检查失败"
        if job is not None:
            candidate_repository.complete_job(conn, job["id"], error_message=message)
        if isinstance(exc, ValueError):
            raise
        raise RuntimeError(message) from exc
    finally:
        conn.close()


async def enrich_openalex(
    candidate_ids: list[int], *, collector: Any | None = None,
    arxiv_collector: Any | None = None, semantic_collector: Any | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not 1 <= len(candidate_ids) <= 20:
        raise ValueError("OpenAlex 单次补全数量必须在 1–20 之间")
    if len(set(candidate_ids)) != len(candidate_ids) or any(value < 1 for value in candidate_ids):
        raise ValueError("补全候选 ID 无效或重复")

    conn = get_active_connection()
    job = None
    try:
        selected = []
        for candidate_id in candidate_ids:
            candidate = candidate_repository.get_candidate(conn, candidate_id)
            if candidate is None:
                raise ValueError(f"候选 #{candidate_id} 不存在")
            doi = candidate.get("source_facts", {}).get("doi")
            if (
                candidate["status"] != "pending"
                or candidate["source_kind"] != "crossref_ieee"
                or not isinstance(doi, str)
                or candidate.get("canonical_id") != f"doi:{doi}"
            ):
                raise ValueError(f"候选 #{candidate_id} 不是可补全的 Crossref DOI 候选")
            selected.append((candidate, doi))

        query = {
            "candidates": [
                {"candidate_id": candidate["id"], "doi": doi, "title": candidate["title"][:300]}
                for candidate, doi in selected
            ]
        }
        job = candidate_repository.create_job(
            conn, collector="openalex_enrichment", query=query
        )
        try:
            async with asyncio.timeout(25):
                result = await (collector or OpenAlexEnrichmentCollector()).enrich(
                    [doi for _, doi in selected]
                )
        except TimeoutError as exc:
            raise RuntimeError("OpenAlex 补全超时（总计 25 秒）") from exc

        fallback = []
        for candidate, doi in selected:
            openalex_facts = result.records_by_doi.get(doi)
            if openalex_facts is None or not openalex_facts.get("abstract"):
                fallback.append({
                    "candidate_id": candidate["id"], "doi": doi,
                    "title": candidate["title"],
                    "authors": candidate.get("source_facts", {}).get("authors", []),
                })
        arxiv_matches = {}
        arxiv_error = None
        if fallback:
            try:
                async with asyncio.timeout(25):
                    arxiv_result = await (
                        arxiv_collector or ArxivVersionCollector()
                    ).match(fallback)
                arxiv_matches = arxiv_result.records_by_candidate_id
            except Exception as exc:
                arxiv_error = str(exc).strip()[:1_000] or "arXiv 版本匹配失败"
        semantic_candidates = [
            candidate for candidate in fallback
            if candidate["candidate_id"] not in arxiv_matches
        ]
        semantic_records = {}
        semantic_error = None
        if semantic_candidates:
            try:
                async with asyncio.timeout(25):
                    semantic_result = await (
                        semantic_collector or SemanticScholarEnrichmentCollector()
                    ).enrich([candidate["doi"] for candidate in semantic_candidates])
                semantic_records = semantic_result.records_by_doi
            except Exception as exc:
                semantic_error = str(exc).strip()[:1_000] or "Semantic Scholar 补全失败"

        succeeded = 0
        attempted_at = datetime.now(timezone.utc).isoformat()
        for candidate, doi in selected:
            facts = result.records_by_doi.get(doi)
            if facts is None:
                candidate_repository.create_source_record(conn, {
                    "candidate_id": candidate["id"], "job_id": job["id"],
                    "source_kind": "openalex", "status": "failed", "facts": {"doi": doi},
                    "error_message": "OpenAlex 未返回该 DOI", "fetched_at": attempted_at,
                })
                continue
            succeeded += 1
            candidate_repository.create_source_record(conn, {
                "candidate_id": candidate["id"], "job_id": job["id"],
                "source_kind": "openalex", "source_record_id": facts["source_record_id"],
                "status": "succeeded", "facts": facts, "fetched_at": facts["fetched_at"],
            })
        for candidate_data in fallback:
            candidate_id = candidate_data["candidate_id"]
            facts = arxiv_matches.get(candidate_id)
            if facts is None:
                candidate_repository.create_source_record(conn, {
                    "candidate_id": candidate_id, "job_id": job["id"],
                    "source_kind": "arxiv_version", "status": "failed",
                    "facts": {"doi": candidate_data["doi"], "title": candidate_data["title"]},
                    "error_message": arxiv_error or "未找到标题与作者均严格匹配的 arXiv 预印本",
                    "fetched_at": attempted_at,
                })
                continue
            candidate_repository.create_source_record(conn, {
                "candidate_id": candidate_id, "job_id": job["id"],
                "source_kind": "arxiv_version", "source_record_id": facts["source_record_id"],
                "status": "succeeded", "facts": facts, "fetched_at": facts["fetched_at"],
            })
        for candidate_data in semantic_candidates:
            facts = semantic_records.get(candidate_data["doi"])
            if facts is None:
                candidate_repository.create_source_record(conn, {
                    "candidate_id": candidate_data["candidate_id"], "job_id": job["id"],
                    "source_kind": "semantic_scholar", "status": "failed",
                    "facts": {"doi": candidate_data["doi"]},
                    "error_message": semantic_error or "Semantic Scholar 未返回该 DOI",
                    "fetched_at": attempted_at,
                })
                continue
            candidate_repository.create_source_record(conn, {
                "candidate_id": candidate_data["candidate_id"], "job_id": job["id"],
                "source_kind": "semantic_scholar", "source_record_id": facts["source_record_id"],
                "status": "succeeded", "facts": facts, "fetched_at": facts["fetched_at"],
            })
        failed = len(selected) - succeeded
        arxiv_succeeded = len(arxiv_matches)
        job = candidate_repository.complete_job(
            conn, job["id"], candidate_count=succeeded,
            result={"requested_count": len(selected), "succeeded_count": succeeded,
                    "failed_count": failed, "partial": succeeded > 0 and failed > 0,
                    "arxiv_checked_count": len(fallback),
                    "arxiv_succeeded_count": arxiv_succeeded,
                    "arxiv_failed_count": len(fallback) - arxiv_succeeded,
                    "semantic_checked_count": len(semantic_candidates),
                    "semantic_succeeded_count": len(semantic_records),
                    "semantic_failed_count": len(semantic_candidates) - len(semantic_records)},
        )
        conn.commit()
        return job, [
            candidate_repository.get_candidate(conn, candidate["id"])
            for candidate, _ in selected
        ]
    except Exception as exc:
        conn.rollback()
        message = str(exc).strip()[:1_000] or "OpenAlex 补全失败"
        if job is not None:
            candidate_repository.complete_job(conn, job["id"], error_message=message)
        if isinstance(exc, ValueError):
            raise
        raise RuntimeError(message) from exc
    finally:
        conn.close()


async def discover_crossref(
    query: dict[str, Any], *, collector: Any | None = None
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    normalized = {
        **query,
        "intent": query.get("intent", "topic"),
        "query": " ".join(str(query.get("query", "")).split()),
        "container_title": " ".join(str(query.get("container_title") or "").split()) or None,
        "issn": str(query.get("issn") or "").replace("-", "").upper() or None,
        "date_basis": query.get("date_basis", "indexed"),
    }
    if len(normalized["query"]) > 200:
        raise ValueError("搜索内容不能超过 200 个字符")
    if normalized["intent"] not in {"topic", "author", "journal_latest", "exact"}:
        raise ValueError("搜索意图无效")
    if normalized["intent"] in {"topic", "author", "exact"} and not normalized["query"]:
        raise ValueError("该搜索方式需要搜索内容")
    if normalized["intent"] == "journal_latest" and not (
        normalized["container_title"] or normalized["issn"]
    ):
        raise ValueError("查看指定期刊最新论文需要期刊名称或 ISSN")
    if normalized.get("scope") not in {"journal", "journal_conference"}:
        raise ValueError("文献类型范围无效")
    if normalized.get("sort") not in {"relevance", "published", "indexed"}:
        raise ValueError("排序方式无效")
    if normalized["date_basis"] not in {"published", "indexed"}:
        raise ValueError("日期依据无效")
    if not 1 <= int(normalized.get("limit", 0)) <= 50:
        raise ValueError("单次发现数量必须在 1–50 之间")
    if normalized["intent"] != "exact" and not (
        normalized.get("date_from") and normalized.get("date_to")
    ):
        raise ValueError("该搜索方式需要日期范围")
    if normalized.get("date_from") and normalized.get("date_to") and normalized["date_from"] > normalized["date_to"]:
        raise ValueError("开始日期不能晚于结束日期")
    conn = get_active_connection()
    job = candidate_repository.create_job(conn, collector="crossref_ieee", query=normalized)
    try:
        try:
            async with asyncio.timeout(25):
                result = await (collector or CrossrefDiscoveryCollector()).search(normalized)
        except TimeoutError as exc:
            raise RuntimeError("Crossref 搜索超时（总计 25 秒）") from exc
        candidates = []
        for record in result.records:
            normalized_text = normalize_text(record.content_text)
            if not normalized_text:
                continue
            canonical_id = record.source_facts["canonical_id"]
            previous = candidate_repository.find_latest_by_canonical_id(conn, canonical_id)
            identity_type, identity_value = canonical_id.split(":", 1)
            existing_item = item_repository.find_by_external_identity(conn, identity_type, identity_value)
            facts = dict(record.source_facts)
            facts["existing_candidate_id"] = previous["id"] if previous else None
            facts["existing_candidate_status"] = previous["status"] if previous else None
            facts["existing_candidate_item_id"] = previous["accepted_item_id"] if previous else None
            facts["existing_candidate_seen_at"] = previous["created_at"] if previous else None
            facts["existing_item_id"] = existing_item["id"] if existing_item else None
            candidates.append(candidate_repository.create_candidate(conn, {
                "job_id": job["id"], "title": record.title, "content_text": normalized_text,
                "summary": record.summary, "source_kind": "crossref_ieee",
                "source_url": record.source_url, "canonical_id": canonical_id,
                "content_hash": hashlib.sha256(normalized_text.encode("utf-8")).hexdigest(),
                "source_facts": facts,
            }))
        metadata = {
            "total_results": result.total_results, "skipped_count": result.skipped_count,
            "truncated": result.truncated, "empty": not candidates,
        }
        job = candidate_repository.complete_job(
            conn, job["id"], candidate_count=len(candidates), result=metadata
        )
        conn.commit()
        return job, candidates
    except Exception as exc:
        conn.rollback()
        message = str(exc).strip()[:1_000] or "Crossref 搜索失败"
        candidate_repository.complete_job(conn, job["id"], error_message=message)
        if isinstance(exc, ValueError):
            raise
        raise RuntimeError(message) from exc
    finally:
        conn.close()


async def discover_arxiv(
    query: str, *, limit: int = 10, collector: Any | None = None
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    normalized_query = " ".join(query.split())
    if not normalized_query:
        raise ValueError("搜索词不能为空")
    if len(normalized_query) > 200:
        raise ValueError("搜索词不能超过 200 字符")
    if not 1 <= limit <= 20:
        raise ValueError("单次发现数量必须在 1–20 之间")
    conn = get_active_connection()
    job = candidate_repository.create_job(
        conn, collector="arxiv_api", query={"query": normalized_query, "limit": limit}
    )
    try:
        try:
            async with asyncio.timeout(25):
                records = await (collector or ArxivDiscoveryCollector()).search(
                    normalized_query, limit
                )
        except TimeoutError as exc:
            raise RuntimeError("arXiv 公开 API 搜索超时（总计 25 秒）") from exc
        candidates = []
        for record in records:
            normalized = normalize_text(record.content_text)
            if not normalized:
                continue
            arxiv_id = record.source_facts.get("arxiv_id", "")
            canonical_id = f"arxiv:{arxiv_id.lower().split('v', 1)[0]}"
            previous = candidate_repository.find_latest_by_canonical_id(conn, canonical_id)
            existing_item = item_repository.find_by_external_identity(
                conn, "arxiv", canonical_id.split(":", 1)[1]
            )
            facts = dict(record.source_facts)
            facts.update({
                "canonical_id": canonical_id,
                "existing_candidate_id": previous["id"] if previous else None,
                "existing_candidate_status": previous["status"] if previous else None,
                "existing_candidate_item_id": previous["accepted_item_id"] if previous else None,
                "existing_candidate_seen_at": previous["created_at"] if previous else None,
                "existing_item_id": existing_item["id"] if existing_item else None,
            })
            candidates.append(candidate_repository.create_candidate(conn, {
                "job_id": job["id"],
                "title": record.title,
                "content_text": normalized,
                "summary": record.summary,
                "source_kind": "arxiv_api",
                "source_url": record.source_url,
                "canonical_id": canonical_id,
                "content_hash": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
                "source_facts": facts,
            }))
        job = candidate_repository.complete_job(
            conn, job["id"], candidate_count=len(candidates)
        )
        return job, candidates
    except Exception as exc:
        conn.rollback()
        message = str(exc).strip()[:1_000] or "arXiv 公开 API 搜索失败"
        candidate_repository.complete_job(conn, job["id"], error_message=message)
        if isinstance(exc, ValueError):
            raise
        raise RuntimeError(message) from exc
    finally:
        conn.close()
