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
        result = await analyzer.review_with_prompt(full_prompt)
    except Exception as e:
        return {"reply": f"AI 调用失败: {str(e)[:200]}", "error": True}

    if not result:
        return {"reply": "AI 未返回有效响应", "error": True}

    # 尝试解析为 JSON 并格式化
    try:
        parsed = json.loads(result)
        # 如果是结构化结果，格式化为可读文本
        lines = []
        if "hot_topics" in parsed:
            lines.append(f"🔥 热门方向: {parsed['hot_topics']}")
        if "tech_trends" in parsed:
            lines.append(f"💡 技术趋势: {parsed['tech_trends']}")
        if "recommendations" in parsed:
            lines.append("⭐ 推荐关注:")
            for r in parsed["recommendations"]:
                lines.append(f"  · {r.get('title', '')} — {r.get('reason', '')}")
        if "innovation" in parsed:
            lines.append(f"💡 创新点: {parsed['innovation']}")
        if "technologies" in parsed:
            techs = parsed["technologies"]
            lines.append(f"🛠 技术: {', '.join(techs if isinstance(techs, list) else [techs])}")
        if "has_code" in parsed:
            lines.append(f"🔗 代码: {parsed.get('code_url') or '未提及'}")
        if lines:
            return {"reply": "\n".join(lines)}
    except (json.JSONDecodeError, TypeError):
        pass

    # 纯文本回复
    return {"reply": result.strip('"')}
