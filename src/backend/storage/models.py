"""
Pydantic 数据模型。定义 API 请求/响应的数据结构。
"""
from pydantic import AnyHttpUrl, BaseModel, Field, RootModel, field_validator
from typing import Annotated, Optional, List, Literal


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
    source_ids: List[int] = Field(min_length=1, max_length=20)
    mode: Literal["new", "all"] = "new"
    keywords: str = ""       # 空格分隔的关键词
    sort_mode: Literal["newest", "hottest"] = "newest"


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
    ai: AIConfig = Field(default_factory=AIConfig)
    crawl: CrawlConfig = Field(default_factory=CrawlConfig)


# ---- Stats ----

class Stats(BaseModel):
    material_count: int = 0
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


# ---- Generic materials ----

MaterialType = Literal["auto", "general", "paper", "job", "debug"]
StoredMaterialType = Literal["general", "paper", "job", "debug"]
MaterialStatus = Literal["inbox", "active", "archived"]
ShortTag = Annotated[str, Field(min_length=1, max_length=50)]


class MaterialCreate(BaseModel):
    content_text: str = Field(min_length=1, max_length=200_000)
    title: Optional[str] = Field(None, max_length=300)
    item_type: MaterialType = "auto"
    source_url: Optional[AnyHttpUrl] = None
    tags: List[ShortTag] = Field(default_factory=list, max_length=50)


class MaterialUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=300)
    item_type: Optional[StoredMaterialType] = None
    status: Optional[MaterialStatus] = None
    tags: Optional[List[ShortTag]] = Field(None, max_length=50)


MaterialAnalysisKind = Literal["classify", "extract"]
MaterialInputField = Literal[
    "title", "content_text", "accepted_extraction", "item_type", "tags", "source_url"
]


class MaterialAnalysisRequest(BaseModel):
    analysis_type: MaterialAnalysisKind
    input_fields: List[MaterialInputField] = Field(min_length=1, max_length=6)


class MaterialComparisonRequest(BaseModel):
    item_ids: List[int] = Field(min_length=2, max_length=20)
    input_fields: List[MaterialInputField] = Field(min_length=1, max_length=6)


class PublicURLImportRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2_000)


class TemplateConfirmationRequest(RootModel[dict[str, Optional[str]]]):
    @field_validator("root")
    @classmethod
    def validate_template_fields(cls, value):
        if len(value) > 20:
            raise ValueError("模板字段不能超过 20 个")
        if any(field_value is not None and len(field_value) > 4_000 for field_value in value.values()):
            raise ValueError("模板字段不能超过 4000 个字符")
        return value


class ArxivDiscoveryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(10, ge=1, le=20)
