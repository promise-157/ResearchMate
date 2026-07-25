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
from api.routes import journals, papers, crawl, cart, settings, stats, docs, workspaces

app.include_router(journals.router, prefix="/api", tags=["journals"])
app.include_router(papers.router, prefix="/api", tags=["papers"])
app.include_router(crawl.router, prefix="/api", tags=["crawl"])
app.include_router(cart.router, prefix="/api", tags=["cart"])
app.include_router(settings.router, prefix="/api", tags=["settings"])
app.include_router(stats.router, prefix="/api", tags=["stats"])
app.include_router(docs.router, prefix="/api", tags=["docs"])
app.include_router(workspaces.router, prefix="/api", tags=["workspaces"])


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


# ---- 生产模式：serve 前端静态文件 ----
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from config import get as config_get

frontend_dist = config_get("frontend", "dist_dir")
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
