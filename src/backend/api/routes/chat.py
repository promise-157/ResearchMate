"""通用 AI 聊天端点"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List

from storage.database import dict_from_row
from storage.workspace import get_active_connection

router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    paper_ids: List[int] = Field(default_factory=list, max_length=12)


@router.post("/chat")
async def chat(req: ChatRequest):
    """通用 AI 对话。message 是用户输入，context 是当前数据上下文。"""
    from config import get as config_get
    from processors.registry import get as get_processor

    api_key = config_get("ai", "api_key")
    if not api_key and config_get("ai", "api_type") != "ollama":
        return {"reply": "未配置 API Key，请在「全局设置 → AI 配置」中填写", "error": True}

    analyzer = get_processor("llm")
    if not analyzer:
        return {"reply": "AI 分析器未加载", "error": True}

    full_prompt = _build_prompt(req)

    try:
        reply = await analyzer.chat(full_prompt)
    except Exception as e:
        return {"reply": f"AI 调用失败: {str(e)[:200]}", "error": True}

    if not reply:
        return {"reply": "AI 未返回有效响应", "error": True}

    return {"reply": reply}


def _build_prompt(req: ChatRequest) -> str:
    """Load explicitly selected papers server-side and bound external context."""
    if not req.paper_ids:
        return req.message

    placeholders = ",".join("?" for _ in req.paper_ids)
    conn = get_active_connection()
    rows = conn.execute(
        f"SELECT id, title, authors, abstract, journal_name, publish_year, paper_url "
        f"FROM papers WHERE id IN ({placeholders})",
        req.paper_ids,
    ).fetchall()
    conn.close()
    papers_by_id = {row["id"]: dict_from_row(row) for row in rows}

    blocks = []
    for paper_id in req.paper_ids:
        paper = papers_by_id.get(paper_id)
        if not paper:
            continue
        blocks.append(
            "\n".join([
                f"[paper_id={paper['id']}] {paper['title']}",
                f"Authors: {paper.get('authors') or '[]'}",
                f"Source: {paper.get('journal_name') or ''} {paper.get('publish_year') or ''}",
                f"URL: {paper.get('paper_url') or ''}",
                f"Abstract: {(paper.get('abstract') or '')[:1200]}",
            ])
        )

    if not blocks:
        return req.message
    return (
        "Use only the attached paper metadata below as evidence. Distinguish source facts "
        "from your inference, and do not invent missing full-text details.\n\n"
        + "\n\n".join(blocks)
        + f"\n\nUser request: {req.message}"
    )
