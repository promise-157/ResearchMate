"""
FastAPI 应用入口。初始化、CORS、挂载路由。
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routes import cart, chat, crawl, discoveries, docs, items, journals, keywords, papers, settings, stats, url_imports, workspace_reviews, workspaces
from config import get
from storage.database import init_db

app = FastAPI(
    title="ResearchMate API",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS is needed only for the local Vite development server. Keeping this
# allowlist narrow prevents arbitrary websites from driving the local API.
dev_port = get("frontend", "dev_port") or 5173
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://127.0.0.1:{dev_port}",
        f"http://localhost:{dev_port}",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(journals.router, prefix="/api", tags=["journals"])
app.include_router(papers.router, prefix="/api", tags=["papers"])
app.include_router(crawl.router, prefix="/api", tags=["crawl"])
app.include_router(cart.router, prefix="/api", tags=["cart"])
app.include_router(settings.router, prefix="/api", tags=["settings"])
app.include_router(stats.router, prefix="/api", tags=["stats"])
app.include_router(docs.router, prefix="/api", tags=["docs"])
app.include_router(workspaces.router, prefix="/api", tags=["workspaces"])
app.include_router(workspace_reviews.router, prefix="/api", tags=["workspace-reviews"])
app.include_router(keywords.router, prefix="/api", tags=["keywords"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(items.router, prefix="/api", tags=["items"])
app.include_router(url_imports.router, prefix="/api", tags=["url-imports"])
app.include_router(discoveries.router, prefix="/api", tags=["discoveries"])


@app.on_event("startup")
def on_startup():
    init_db()
    from config import scrub_persisted_secrets
    scrub_persisted_secrets()
    from crawlers.registry import init_registry as init_crawlers
    from processors.registry import init_registry as init_processors
    init_crawlers()
    init_processors()
    from storage.workspace import recover_interrupted_runs
    recover_interrupted_runs()


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---- 生产模式：serve 前端静态文件 ----
frontend_dist = get("frontend", "dist_dir")
if os.path.isdir(frontend_dist):
    # 先挂载静态资源（JS/CSS/图片等），不加 html=True 避免拦截 API
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    # SPA fallback：所有非 API 的 GET 请求返回 index.html
    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        file_path = os.path.join(frontend_dist, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_dist, "index.html"))
