"""爬取触发 + 状态查询"""
from fastapi import APIRouter
from storage.models import CrawlRequest, CrawlStatus

router = APIRouter()

# 内存中的爬取状态（单用户，不需要持久化状态机）
_crawl_state = CrawlStatus()


@router.post("/crawl")
def start_crawl(body: CrawlRequest):
    global _crawl_state
    if _crawl_state.status in ("crawling", "analyzing"):
        return {"ok": False, "message": "已有爬取任务在进行中"}

    _crawl_state = CrawlStatus(status="crawling", percentage=0, message="")
    # TODO: 阶段九实现实际爬取逻辑
    # 这里先返回接受任务
    return {"ok": True, "message": "爬取任务已启动"}


@router.get("/crawl/status")
def get_crawl_status():
    return _crawl_state
