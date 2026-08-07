"""Explicit acceptance workflow for deterministic extraction results."""
from typing import Any

from storage import accepted_extractions as accepted_repository
from storage import items as item_repository
from storage.workspace import get_active_connection


ACCEPTABLE_RUNS = {"ocr": "text"}


def accept_extraction(item_id: int, run_id: int) -> dict[str, Any] | None:
    conn = get_active_connection()
    try:
        item = item_repository.get_item(conn, item_id)
        if not item:
            return None
        run = item_repository.get_extraction_run(conn, run_id)
        if not run or run["item_id"] != item_id:
            raise ValueError("提取运行不存在或不属于该资料")
        result_field = ACCEPTABLE_RUNS.get(run["run_kind"])
        if not result_field or run["provider"] != "local":
            raise ValueError("只有受支持的本地确定性提取结果可以接受")
        if run["status"] != "succeeded" or not run["result"]:
            raise ValueError("只有成功的提取结果可以接受")
        text = str(run["result"].get(result_field, "")).strip()
        if not text:
            raise ValueError("提取结果没有可接受的文本")
        return accepted_repository.accept(
            conn,
            item_id=item_id,
            extraction_kind=run["run_kind"],
            run_id=run_id,
            text_value=text,
        )
    finally:
        conn.close()
