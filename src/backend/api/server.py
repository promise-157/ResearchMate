"""
FastAPI 应用入口。初始化、CORS、挂载路由。
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from storage.database import init_db
from config import get

app = FastAPI(
    title="ResearchMate API",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS — 允许前端开发服务器跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from api.routes import journals, papers, crawl, cart, settings, stats

app.include_router(journals.router, prefix="/api", tags=["journals"])
app.include_router(papers.router, prefix="/api", tags=["papers"])
app.include_router(crawl.router, prefix="/api", tags=["crawl"])
app.include_router(cart.router, prefix="/api", tags=["cart"])
app.include_router(settings.router, prefix="/api", tags=["settings"])
app.include_router(stats.router, prefix="/api", tags=["stats"])


@app.on_event("startup")
def on_startup():
    init_db()
    from crawlers.registry import init_registry as init_crawlers
    from processors.registry import init_registry as init_processors
    init_crawlers()
    init_processors()


@app.get("/api/health")
def health():
    return {"status": "ok"}
