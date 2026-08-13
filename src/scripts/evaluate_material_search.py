"""Offline M15 benchmark for current LIKE search versus an FTS5 trigram prototype.

The script creates disposable workspace-shaped SQLite databases. It never reads a
configured workspace or source data. Results are intended for architectural
evaluation, not as a timing assertion in the automated test suite.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "src" / "backend"
sys.path.insert(0, str(BACKEND))

from storage import items as item_repository  # noqa: E402
from storage.workspace import _init_workspace_db  # noqa: E402


@dataclass(frozen=True)
class SearchCase:
    name: str
    query: str
    include_accepted: bool = False
    item_type: str | None = None
    status: str | None = None


CASES = (
    SearchCase("common_chinese", "资料"),
    SearchCase("selective_chinese", "向量检索"),
    SearchCase("selective_english_casefold", "connectiontimeout"),
    SearchCase("literal_wildcards", "%_literal"),
    SearchCase("accepted_ocr_off", "票据识别"),
    SearchCase("accepted_ocr_on", "票据识别", include_accepted=True),
    SearchCase("type_and_status", "依赖冲突", item_type="debug", status="active"),
    SearchCase("two_character_fallback", "错误"),
    SearchCase("one_character_fallback", "错"),
)


def _fixture_row(index: int) -> tuple[Any, ...]:
    item_types = ("general", "paper", "debug", "job")
    statuses = ("inbox", "active", "archived")
    item_type = item_types[index % len(item_types)]
    status = statuses[index % len(statuses)]
    title = f"资料 {index:06d} — local workspace note"
    fragments = [
        "这是用于检索评估的本地资料，包含中文段落和 English tokens。",
        f"batch marker {index % 997}; project ResearchMate; ordinary content.",
    ]
    if index % 211 == 0:
        fragments.append("向量检索只在有证据时考虑，不自动启用 embedding。")
    if index % 307 == 0:
        fragments.append("ConnectionTimeout occurred while reading an offline fixture.")
    if index % 401 == 0:
        fragments.append("The literal token is 100%_literal and wildcards are data.")
    if index % 173 == 2:
        fragments.append("错误：依赖冲突；环境：Python；方案：固定版本。")
    content = "\n".join(fragments)
    return (
        item_type,
        title,
        content,
        content[:240],
        "text_import",
        status,
        "[]",
        "{}",
        f"fixture-{index:08d}",
    )


def _populate(conn: sqlite3.Connection, size: int) -> None:
    sql = """INSERT INTO items
             (item_type, title, content_text, summary, source_kind, status,
              tags_json, metadata_json, content_hash)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"""
    batch_size = 1_000
    for start in range(0, size, batch_size):
        conn.executemany(sql, (_fixture_row(i) for i in range(start, min(size, start + batch_size))))
    accepted_item_ids = list(range(11, size + 1, 251))
    for item_id in accepted_item_ids:
        run_id = conn.execute(
            """INSERT INTO extraction_runs
               (item_id, processor, processor_version, run_kind, status, input_hash,
                result_json, provider, model, prompt_version)
               VALUES (?, 'local_tesseract', '1', 'ocr', 'succeeded', ?, ?,
                       'local', 'tesseract', 'none')""",
            (
                item_id,
                f"ocr-{item_id}",
                json.dumps({"text": f"票据识别 OCR fixture {item_id}"}, ensure_ascii=False),
            ),
        ).lastrowid
        conn.execute(
            """INSERT INTO accepted_extractions
               (item_id, extraction_kind, run_id, text_value)
               VALUES (?, 'ocr', ?, ?)""",
            (item_id, run_id, f"票据识别 OCR fixture {item_id}"),
        )
    conn.commit()


def _build_fts(conn: sqlite3.Connection) -> float:
    started = time.perf_counter()
    conn.execute(
        """CREATE VIRTUAL TABLE material_search_fts USING fts5(
               item_id UNINDEXED, title, content_text, accepted_text,
               tokenize='trigram'
           )"""
    )
    conn.execute(
        """INSERT INTO material_search_fts(item_id, title, content_text, accepted_text)
           SELECT items.id, items.title, items.content_text,
                  COALESCE(group_concat(accepted_extractions.text_value, char(10)), '')
           FROM items
           LEFT JOIN accepted_extractions ON accepted_extractions.item_id = items.id
           GROUP BY items.id"""
    )
    conn.commit()
    return (time.perf_counter() - started) * 1_000


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _like_ids(conn: sqlite3.Connection, case: SearchCase) -> list[int]:
    escaped = _escape_like(case.query)
    clauses = ["(items.title LIKE ? ESCAPE '\\' OR items.content_text LIKE ? ESCAPE '\\'"]
    params: list[Any] = [f"%{escaped}%", f"%{escaped}%"]
    if case.include_accepted:
        clauses[0] += (
            " OR EXISTS (SELECT 1 FROM accepted_extractions ae "
            "WHERE ae.item_id = items.id AND ae.text_value LIKE ? ESCAPE '\\')"
        )
        params.append(f"%{escaped}%")
    clauses[0] += ")"
    if case.item_type:
        clauses.append("items.item_type = ?")
        params.append(case.item_type)
    if case.status:
        clauses.append("items.status = ?")
        params.append(case.status)
    rows = conn.execute(
        f"SELECT items.id FROM items WHERE {' AND '.join(clauses)} ORDER BY items.id",
        params,
    ).fetchall()
    return [row[0] for row in rows]


def _fts_ids(conn: sqlite3.Connection, case: SearchCase) -> list[int]:
    # FTS5 trigram cannot match substrings shorter than three Unicode characters.
    if len(case.query) < 3:
        return _like_ids(conn, case)
    columns = "{title content_text accepted_text}" if case.include_accepted else "{title content_text}"
    match = f'{columns} : "{case.query.replace(chr(34), chr(34) * 2)}"'
    clauses = ["material_search_fts MATCH ?"]
    params: list[Any] = [match]
    if case.item_type:
        clauses.append("items.item_type = ?")
        params.append(case.item_type)
    if case.status:
        clauses.append("items.status = ?")
        params.append(case.status)
    rows = conn.execute(
        f"""SELECT items.id
            FROM material_search_fts
            JOIN items ON items.id = material_search_fts.item_id
            WHERE {' AND '.join(clauses)} ORDER BY items.id""",
        params,
    ).fetchall()
    return [row[0] for row in rows]


def _time_ms(operation: Callable[[], Any], repeats: int) -> dict[str, float]:
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        operation()
        samples.append((time.perf_counter() - started) * 1_000)
    ordered = sorted(samples)
    p95_index = min(len(ordered) - 1, int(len(ordered) * 0.95))
    return {
        "median_ms": round(statistics.median(samples), 3),
        "p95_ms": round(ordered[p95_index], 3),
    }


def evaluate_size(size: int, repeats: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="researchmate-search-") as temp_dir:
        db_path = Path(temp_dir) / f"materials-{size}.db"
        _init_workspace_db(str(db_path))
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        _populate(conn, size)

        # Exercise the production repository at least once for contract drift.
        production_probe = item_repository.list_items(
            conn, query="向量检索", page=1, page_size=20
        )
        page_size = conn.execute("PRAGMA page_size").fetchone()[0]
        baseline_pages = conn.execute("PRAGMA page_count").fetchone()[0]
        build_ms = _build_fts(conn)
        cases = []
        for case in CASES:
            like_ids = _like_ids(conn, case)
            fts_ids = _fts_ids(conn, case)
            cases.append({
                **asdict(case),
                "matches": len(like_ids),
                "equivalent": like_ids == fts_ids,
                "like": _time_ms(lambda case=case: _like_ids(conn, case), repeats),
                "fts": _time_ms(lambda case=case: _fts_ids(conn, case), repeats),
                "uses_like_fallback": len(case.query) < 3,
            })
        page_count = conn.execute("PRAGMA page_count").fetchone()[0]
        conn.close()
        baseline_mib = baseline_pages * page_size / 1024 / 1024
        with_fts_mib = page_count * page_size / 1024 / 1024
        return {
            "size": size,
            "database_mib_before_fts": round(baseline_mib, 2),
            "database_mib_with_fts": round(with_fts_mib, 2),
            "fts_size_increase_percent": round(
                (with_fts_mib - baseline_mib) / baseline_mib * 100, 1
            ),
            "fts_build_ms": round(build_ms, 3),
            "production_probe_total": production_probe["total"],
            "all_equivalent": all(case["equivalent"] for case in cases),
            "cases": cases,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="+", default=[10_000, 50_000])
    parser.add_argument("--repeats", type=int, default=15)
    args = parser.parse_args()
    report = {
        "sqlite_version": sqlite3.sqlite_version,
        "fixture": "synthetic multilingual workspace-shaped records",
        "repeats": args.repeats,
        "results": [evaluate_size(size, args.repeats) for size in args.sizes],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
