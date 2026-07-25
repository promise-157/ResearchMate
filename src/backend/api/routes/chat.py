"""通用 AI 聊天端点"""
import json
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, Any

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    scope: str = "工作区"
    context: Dict[str, Any] = {}


@router.post("/chat")
async def chat(req: ChatRequest):
    """通用 AI 对话。message 是用户输入，context 是当前数据上下文。"""
    from config import get as config_get
    from processors.registry import get as get_processor

    api_key = config_get("ai", "api_key")
    if not api_key:
        return {"reply": "未配置 API Key，请在「全局设置 → AI 配置」中填写", "error": True}

    analyzer = get_processor("llm")
    if not analyzer:
        return {"reply": "AI 分析器未加载", "error": True}

    # 构建带上下文的系统提示
    context_str = ""
    if req.context.get("paper_count"):
        context_str = f"\n当前可访问数据: {req.context.get('paper_count')} 篇论文"
        if req.context.get("top_keywords"):
            context_str += f"\n关键词: {req.context.get('top_keywords')}"

    full_prompt = req.message
    if context_str:
        full_prompt = context_str + "\n\n用户指令: " + req.message

    try:
        reply = await analyzer.chat(full_prompt)
    except Exception as e:
        return {"reply": f"AI 调用失败: {str(e)[:200]}", "error": True}

    if not reply:
        return {"reply": "AI 未返回有效响应", "error": True}

    return {"reply": reply}
