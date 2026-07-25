"""
Pydantic 数据模型。定义 API 请求/响应的数据结构。
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ---- Journal Sources ----

class JournalSourceCreate(BaseModel):
    url: str
    label: Optional[str] = None


class JournalSource(BaseModel):
    id: int
    url: str
    label: Optional[str] = None
    last_crawled_at: Optional[str] = None
    last_paper_count: int = 0
    created_at: Optional[str] = None


# ---- Papers ----

class PaperBase(BaseModel):
    title: str
    authors: Optional[str] = None         # JSON string
    abstract: Optional[str] = None
    journal_name: Optional[str] = None
    publish_year: Optional[int] = None
    arxiv_id: Optional[str] = None
    paper_url: Optional[str] = None
    has_code: bool = False
    code_url: Optional[str] = None
    ai_innovation: Optional[str] = None
    ai_technologies: Optional[str] = None  # JSON string
    ai_analyzed: bool = False


class Paper(PaperBase):
    id: int
    source_id: Optional[int] = None
    in_cart: bool = False
    created_at: Optional[str] = None


class PaperUpdate(BaseModel):
    in_cart: Optional[bool] = None


# ---- Crawl ----

class CrawlRequest(BaseModel):
    source_ids: List[int]
    mode: str = "new"       # "new" | "all"
    keywords: str = ""       # 空格分隔的关键词
    sort_mode: str = "newest"  # "newest" | "hottest"


class CrawlStatus(BaseModel):
    status: str = "idle"       # idle | crawling | analyzing | done | error
    percentage: int = 0
    message: str = ""


# ---- Crawl Session ----

class CrawlSession(BaseModel):
    id: int
    sources: Optional[str] = None
    paper_count: int = 0
    ai_review: Optional[str] = None
    created_at: Optional[str] = None


# ---- Settings ----

class AIConfig(BaseModel):
    api_type: str = "openai"
    api_key: str = ""
    api_base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o"


class CrawlConfig(BaseModel):
    max_papers_per_source: int = 50
    request_interval: int = 2
    timeout: int = 30


class Settings(BaseModel):
    theme: str = "system"
    ai: AIConfig = AIConfig()
    crawl: CrawlConfig = CrawlConfig()


# ---- Stats ----

class Stats(BaseModel):
    paper_count: int = 0
    cart_count: int = 0
    last_update: Optional[str] = None


# ---- Query Params ----

class PaperQuery(BaseModel):
    q: Optional[str] = None
    has_code: Optional[bool] = None
    in_cart: Optional[bool] = None
    source_id: Optional[int] = None
    sort: str = "newest"
    page: int = 1
    page_size: int = 20
