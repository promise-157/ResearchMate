"""
LLM 分析器。调用 OpenAI 兼容 API 分析论文摘要。
支持: OpenAI, Claude (via Anthropic), Ollama, 自定义兼容接口。
"""
import json
import re
from typing import List, Dict, Optional

import httpx

from processors.base import BaseProcessor
from config import get as config_get

SINGLE_PAPER_PROMPT = """你是一个学术论文评审助手。请阅读以下论文的标题和摘要，严格按 JSON 格式回答。

标题: {title}
摘要: {abstract}

请返回一个 JSON 对象（不要附带其他文字），包含以下字段：
{{
  "has_code": true/false,
  "code_url": "如果摘要中提到 GitHub 链接则提取完整 URL，否则为 null",
  "innovation": "用中文一句话概括论文的核心创新点（20-50字）",
  "technologies": ["技术/方法/模型关键词", "每个关键词10字以内", "最多5个"]
}}"""

BATCH_REVIEW_PROMPT = """你是一个学术会议领域主席。请阅读以下一批论文的标题和摘要（共 {paper_count} 篇），撰写一份简短的综述点评。

论文列表：
{paper_summaries}

请返回一个 JSON 对象（不要附带其他文字），包含以下字段：
{{
  "hot_topics": "这批论文集中讨论的热门方向（20-40字）",
  "recommendations": [
    {{"title": "论文标题", "reason": "推荐理由（15字以内）"}}
  ],
  "tech_trends": "出现频繁的技术/方法关键词汇总（20-40字）"
}}

注意：recommendations 最多推荐 5 篇最有价值的论文（不用作者名，用标题）。"""


class LLMAnalyzer(BaseProcessor):
    """基于 LLM 的论文分析器。"""

    @property
    def name(self) -> str:
        return "llm"

    def _get_client(self) -> httpx.AsyncClient:
        timeout = config_get("crawler", "timeout") or 120
        return httpx.AsyncClient(timeout=timeout)

    def _has_credentials(self) -> bool:
        return (config_get("ai", "api_type") == "ollama" or
                bool((config_get("ai", "api_key") or "").strip()))

    def _api_params(self) -> dict:
        """构建 API 请求参数。"""
        api_type = config_get("ai", "api_type") or "openai"
        base_url = (config_get("ai", "api_base_url") or "").rstrip("/")
        model = config_get("ai", "model") or "gpt-4o"

        # 构建 chat/completions URL
        if api_type == "claude":
            url = f"{base_url}/v1/messages"
        else:
            # OpenAI / DeepSeek / Ollama / 自定义 — 全部 OpenAI 兼容
            url = f"{base_url}/chat/completions"

        return {
            "url": url,
            "model": model,
            "api_type": api_type,
        }

    async def analyze(self, paper: Dict) -> Dict:
        """分析单篇论文。"""
        title = paper.get("title", "")
        abstract = paper.get("abstract", "")
        if not abstract:
            return {"has_code": False, "code_url": None, "innovation": None,
                    "technologies": "[]", "analyzed": True}

        # 检查是否有 API key
        if not self._has_credentials():
            return {"has_code": False, "code_url": None, "innovation": None,
                    "technologies": "[]", "analyzed": False}

        prompt = SINGLE_PAPER_PROMPT.format(title=title, abstract=abstract[:3000])

        result = await self._call_llm(prompt)
        if result:
            return {
                "has_code": result.get("has_code", False),
                "code_url": result.get("code_url"),
                "innovation": result.get("innovation", ""),
                "technologies": json.dumps(result.get("technologies", []), ensure_ascii=False),
                "analyzed": True,
            }
        else:
            return {"has_code": False, "code_url": None, "innovation": None,
                    "technologies": "[]", "analyzed": False}

    async def review_with_prompt(self, prompt: str) -> Optional[str]:
        """直接发送自定义 prompt，返回 AI 回复文本。"""
        if not self._has_credentials():
            print("[llm] WARNING: API key not configured")
            return None
        result = await self._call_llm(prompt)
        if result:
            return json.dumps(result, ensure_ascii=False)
        # 如果 JSON 解析失败，_call_llm 返回 None，这里也返回 None
        # _parse_json 已将原始响应打印到日志
        return None

    async def review(self, papers: List[Dict]) -> Optional[str]:
        """对一批论文进行汇总点评。"""
        if not papers:
            return None

        # 汇总论文摘要（截断以控制 token 消耗）
        summaries = []
        for i, p in enumerate(papers[:30]):  # 最多取 30 篇
            title = p.get("title", "")[:100]
            abstract = (p.get("abstract", "") or "")[:300]
            summaries.append(f"{i + 1}. {title}\n   {abstract}")

        prompt = BATCH_REVIEW_PROMPT.format(
            paper_count=len(papers),
            paper_summaries="\n\n".join(summaries),
        )

        result = await self._call_llm(prompt)
        if result:
            return json.dumps(result, ensure_ascii=False)
        return None

    async def chat(self, prompt: str) -> Optional[str]:
        """对话模式，返回原始文本（不解析 JSON）。"""
        if not self._has_credentials():
            return None
        return await self._call_llm_raw(prompt)

    async def _call_llm_raw(self, prompt: str) -> Optional[str]:
        """调用 LLM API，返回原始响应文本。"""
        api_key = config_get("ai", "api_key") or ""
        if not self._has_credentials():
            return None

        params = self._api_params()
        api_type = params["api_type"]
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if api_type == "claude":
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"

        body = {
            "model": params["model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 1024,
        }
        if api_type == "claude":
            body = {"model": params["model"], "max_tokens": 1024, "temperature": 0.7,
                    "messages": [{"role": "user", "content": prompt}]}

        try:
            async with self._get_client() as client:
                resp = await client.post(params["url"], headers=headers, json=body)
                if resp.status_code != 200:
                    print(f"[llm] API error {resp.status_code}: {resp.text[:200]}")
                    return None
                data = resp.json()
                if api_type == "claude":
                    return data.get("content", [{}])[0].get("text", "")
                return data.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            print(f"[llm] Request failed: {e}")
            return None

    async def _call_llm(self, prompt: str) -> Optional[Dict]:
        """调用 LLM API，返回解析后的 JSON 字典。"""
        api_key = config_get("ai", "api_key") or ""
        if not self._has_credentials():
            print("[llm] WARNING: API key not configured, skipping analysis")
            return None

        params = self._api_params()

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        # Anthropic 需要特殊 header
        api_type = params["api_type"]
        if api_type == "claude":
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"

        body = {
            "model": params["model"],
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 1024,
        }

        # Anthropic 格式转换
        if api_type == "claude":
            body = {
                "model": params["model"],
                "max_tokens": 1024,
                "temperature": 0.3,
                "messages": [{"role": "user", "content": prompt}],
            }

        try:
            async with self._get_client() as client:
                # 如果 API key 为空，跳过
                resp = await client.post(params["url"], headers=headers, json=body)

                if resp.status_code != 200:
                    print(f"[llm] API error {resp.status_code}: {resp.text[:300]}")
                    return None

                data = resp.json()

                # 提取回复文本
                if api_type == "claude":
                    text = data.get("content", [{}])[0].get("text", "")
                else:
                    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                return self._parse_json(text)

        except Exception as e:
            print(f"[llm] Request failed: {e}")
            return None

    def _parse_json(self, text: str) -> Optional[Dict]:
        """从 LLM 回复中提取 JSON 对象。"""
        if not text:
            print("[llm] empty response text")
            return None
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # 尝试从 markdown 代码块提取
        m = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except json.JSONDecodeError:
                pass
        # 尝试用花括号匹配（非贪婪）
        m = re.search(r'\{[\s\S]*\}', text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        print(f"[llm] JSON parse failed. Raw response:\n{text[:500]}")
        return None
