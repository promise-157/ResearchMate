"""工作区管理 API"""
import os
import json as _json
import asyncio
import shutil
import threading
import traceback
from collections import Counter
from datetime import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from storage.database import get_connection as get_main_conn, dict_from_row
from storage.workspace import (
    get_active_path, switch_workspace, create_workspace,
    delete_workspace_file, clear_workspace, WORKSPACE_DIR,
    get_active_connection,
)

router = APIRouter()


@router.get("/workspaces")
def list_workspaces():
    """列出所有工作区 + 当前活跃信息。"""
    conn = get_main_conn()

    # 确保 workspaces 表存在
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS workspaces (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            db_path     TEXT NOT NULL,
            paper_count INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now')),
            opened_at   TEXT DEFAULT (datetime('now'))
        );
    """)

    rows = conn.execute("SELECT * FROM workspaces ORDER BY opened_at DESC").fetchall()
    conn.close()

    active_path = get_active_path()
    return {
        "active_path": active_path,
        "active_name": os.path.basename(active_path).replace(".db", ""),
        "items": [dict_from_row(r) for r in rows],
    }


@router.post("/workspaces")
def create_workspace_api(name: str = ""):
    """创建新工作区。"""
    name = name.strip() or f"workspace_{datetime.now().strftime('%Y%m%d_%H%M')}"
    db_path = create_workspace(name)
    display_name = os.path.basename(db_path).replace(".db", "")

    conn = get_main_conn()
    conn.execute(
        "INSERT INTO workspaces (name, db_path) VALUES (?, ?)",
        (display_name, db_path),
    )
    conn.commit()
    conn.close()

    switch_workspace(db_path)
    return {"ok": True, "name": display_name, "db_path": db_path}


@router.post("/workspaces/load")
def load_workspace_api(db_path: str = ""):
    """切换到指定工作区。"""
    if not db_path or not os.path.isfile(db_path):
        raise HTTPException(status_code=404, detail="工作区文件不存在")

    if not switch_workspace(db_path):
        raise HTTPException(status_code=500, detail="切换失败")

    # 更新最后打开时间
    conn = get_main_conn()
    conn.execute(
        "UPDATE workspaces SET opened_at = ? WHERE db_path = ?",
        (datetime.now().strftime("%Y-%m-%d %H:%M"), db_path),
    )
    conn.commit()
    conn.close()

    return {"ok": True, "db_path": db_path}


@router.delete("/workspaces/{workspace_id}")
def delete_workspace_api(workspace_id: int):
    """删除工作区。"""
    conn = get_main_conn()
    row = conn.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="工作区不存在")

    db_path = row["db_path"]
    conn.execute("DELETE FROM workspaces WHERE id = ?", (workspace_id,))
    conn.commit()
    conn.close()

    delete_workspace_file(db_path)
    return {"ok": True}


@router.get("/workspace/export")
def export_workspace():
    """下载当前工作区 DB 文件。"""
    db_path = get_active_path()
    if not os.path.isfile(db_path):
        raise HTTPException(status_code=404, detail="工作区文件不存在")
    name = os.path.basename(db_path)
    return FileResponse(db_path, media_type="application/octet-stream", filename=name)


@router.post("/workspace/import")
async def import_workspace(file: UploadFile = File(...)):
    """上传工作区 DB 文件并加载。"""
    if not file.filename or not file.filename.endswith(".db"):
        raise HTTPException(status_code=400, detail="请上传 .db 文件")

    _ensure_dir_ws()
    safe_name = file.filename.replace(" ", "_").replace("/", "_")
    dest = os.path.join(str(WORKSPACE_DIR), safe_name)

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # 注册到主DB
    display_name = safe_name.replace(".db", "")
    conn = get_main_conn()
    existing = conn.execute("SELECT id FROM workspaces WHERE db_path = ?", (dest,)).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO workspaces (name, db_path) VALUES (?, ?)",
            (display_name, dest),
        )
    conn.commit()
    conn.close()

    switch_workspace(dest)
    return {"ok": True, "name": display_name, "db_path": dest}


def _ensure_dir_ws():
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/workspaces/current/clear")
def clear_current_workspace():
    """清空当前工作区论文数据。"""
    clear_workspace()

    active_path = get_active_path()
    conn = get_main_conn()
    conn.execute(
        "UPDATE workspaces SET paper_count = 0 WHERE db_path = ?",
        (active_path,),
    )
    conn.commit()
    conn.close()

    return {"ok": True}


@router.post("/workspace/review")
async def trigger_workspace_review():
    """生成工作区 AI 点评（同步等待，返回结果或错误）。"""
    from processors.registry import get as get_processor
    from config import get as config_get

    api_type = config_get("ai", "api_type") or "openai"
    api_key = config_get("ai", "api_key")
    model = config_get("ai", "model") or "unknown"

    if not api_key:
        return {
            "ok": False,
            "error": "未配置 API Key",
            "hint": "请在「全局设置 → AI 配置」中填写 API Key 并等待自动保存",
        }

    analyzer = get_processor("llm")
    if not analyzer:
        return {"ok": False, "error": "AI 分析器未加载"}

    conn = get_active_connection()
    papers = conn.execute(
        "SELECT title, auto_keywords FROM papers"
    ).fetchall()

    if not papers:
        conn.close()
        return {"ok": False, "error": "当前工作区没有论文"}

    papers_list = [dict_from_row(p) for p in papers]
    conn.close()

    # 关键词统计
    counter = Counter()
    for p in papers_list:
        try:
            for k in _json.loads(p.get("auto_keywords", "[]")):
                counter[k] += 1
        except (_json.JSONDecodeError, TypeError):
            pass

    top_kw = counter.most_common(20)
    kw_summary = ", ".join(f"{k}({c})" for k, c in top_kw[:15])
    title_sample = [p["title"][:100] for p in papers_list[:20]]

    prompt = f"""你是一个学术会议领域主席。请基于以下信息撰写简短综述。

关键词频率: {kw_summary}

论文标题样本 ({len(title_sample)}/{len(papers_list)} 篇):
{chr(10).join(f'{i+1}. {t}' for i, t in enumerate(title_sample))}

请返回 JSON（不要附带其他文字）：
{{
  "hot_topics": "这批论文的热门方向（20-40字）",
  "recommendations": [
    {{"title": "论文标题", "reason": "推荐理由（15字以内）"}}
  ],
  "tech_trends": "技术趋势关键词（20-40字）"
}}

注意：recommendations 最多推荐 5 篇。用标题原文，不要翻译。"""

    try:
        review_text = await analyzer.review_with_prompt(prompt)
    except Exception as e:
        return {"ok": False, "error": f"AI 调用失败: {str(e)[:200]}"}

    if not review_text:
        return {
            "ok": False,
            "error": "AI 返回格式异常",
            "hint": f"请查看终端日志确认 API 连通性 (api_type={api_type}, model={model})。如持续失败，请检查模型名称是否正确或 API Base URL 是否需要调整。",
        }

    # 保存到 DB
    conn = get_active_connection()
    conn.execute(
        "INSERT INTO workspace_reviews (task_ids, ai_review) VALUES (?, ?)",
        (_json.dumps([]), review_text),
    )
    conn.commit()
    conn.close()

    # 解析结果返回给前端
    try:
        parsed = _json.loads(review_text)
    except (_json.JSONDecodeError, TypeError):
        parsed = {"raw": review_text}

    return {
        "ok": True,
        "review": parsed,
        "meta": {
            "api_type": api_type,
            "model": model,
            "paper_count": len(papers_list),
            "keywords_used": kw_summary[:100],
        },
    }

