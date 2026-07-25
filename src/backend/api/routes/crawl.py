"""爬取触发 + 状态查询。接入爬虫注册表，实现去重存储。"""
import asyncio
import json
import threading
import traceback
from datetime import datetime

from fastapi import APIRouter

from storage.database import get_connection, dict_from_row
from storage.workspace import get_active_connection as get_ws_conn
from storage.models import CrawlRequest
from crawlers.registry import find_crawler

router = APIRouter()

# 爬取状态（单用户内存状态机）
_status = {"status": "idle", "percentage": 0, "message": ""}


@router.post("/crawl")
def start_crawl(body: CrawlRequest):
    global _status
    if _status["status"] in ("crawling", "analyzing"):
        return {"ok": False, "message": "已有爬取任务在进行中"}

    _status = {"status": "crawling", "percentage": 0, "message": ""}

    # 在后台线程中运行异步爬取
    thread = threading.Thread(
        target=_run_crawl,
        args=(body.source_ids, body.mode, body.keywords, body.sort_mode),
        daemon=True,
    )
    thread.start()
    return {"ok": True, "message": "爬取任务已启动"}


@router.get("/crawl/status")
def get_crawl_status():
    return _status


def _run_crawl(source_ids: list, mode: str, keywords: str = "", sort_mode: str = "newest"):
    """后台线程入口 — 运行 asyncio 爬取任务。"""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_do_crawl(source_ids, mode, keywords, sort_mode))
    except Exception as e:
        global _status
        _status = {
            "status": "error",
            "percentage": 0,
            "message": f"爬取出错: {str(e)}",
        }
        traceback.print_exc()
    finally:
        loop.close()


async def _do_crawl(source_ids: list, mode: str, keywords: str = "", sort_mode: str = "newest"):
    """执行爬取：遍历期刊源 → 爬取 → 去重 → 入库。"""
    global _status
    conn = get_connection()        # 主DB：读期刊源
    ws_conn = get_ws_conn()        # 工作区DB：存论文
    all_new_papers = []

    try:
        # 获取选中的期刊源
        placeholders = ",".join("?" * len(source_ids))
        sources = conn.execute(
            f"SELECT * FROM journal_sources WHERE id IN ({placeholders})",
            source_ids,
        ).fetchall()
        sources = [dict_from_row(s) for s in sources]

        total_sources = len(sources)
        papers_per_source = []

        for idx, source in enumerate(sources):
            _status["message"] = f"正在爬取: {source['label'] or source['url']}"
            _status["percentage"] = int((idx / total_sources) * 60)

            # 找到合适的爬虫
            crawler = find_crawler(source["url"])
            if not crawler:
                continue

            # 爬取
            try:
                papers = await crawler.crawl(source["url"], mode, keywords, sort_mode)
            except Exception as e:
                print(f"[crawl] error crawling {source['url']}: {e}")
                continue

            # 去重 + 入库
            new_count = 0
            for paper in papers:
                if _paper_exists(ws_conn, paper):
                    continue

                # 关键词自动提取
                from processors.keyword_extractor import extract_for_paper
                kw_data = extract_for_paper(paper)
                paper.update(kw_data)

                _insert_paper(ws_conn, paper, source["id"])
                new_count += 1
                all_new_papers.append(paper)

            papers_per_source.append(new_count)

            # 更新期刊源的最后爬取时间
            conn.execute(
                "UPDATE journal_sources SET last_crawled_at = ?, last_paper_count = ? WHERE id = ?",
                (datetime.now().strftime("%Y-%m-%d %H:%M"), new_count, source["id"]),
            )
            conn.commit()

            # 请求间隔
            from config import get as config_get
            interval = config_get("crawler", "request_interval") or 2
            await asyncio.sleep(interval)

        _status["percentage"] = 90
        _status["status"] = "done"
        _status["message"] = f"从 {total_sources} 个源爬取完成，新增 {len(all_new_papers)} 篇"

        # 记录爬取任务到工作区DB
        if all_new_papers:
            ws_conn.execute(
                "INSERT INTO crawl_tasks (source_id, keywords, sort_mode, paper_count) VALUES (?, ?, ?, ?)",
                (source_ids[0] if len(source_ids) == 1 else None,
                 json.dumps(source_ids), "newest", len(all_new_papers)),
            )
        ws_conn.commit()

        # 更新主DB中期刊源的最后爬取时间
        for sid in source_ids:
            conn.execute(
                "UPDATE journal_sources SET last_crawled_at = ?, last_paper_count = ? WHERE id = ?",
                (datetime.now().strftime("%Y-%m-%d %H:%M"), len(all_new_papers), sid),
            )
        conn.commit()

        # 更新主DB工作区计数
        from storage.workspace import get_active_path
        conn.execute(
            "UPDATE workspaces SET paper_count = (SELECT COUNT(*) FROM papers) WHERE db_path = ?",
            (get_active_path(),),
        )
        conn.commit()

    finally:
        conn.close()
        ws_conn.close()


def _paper_exists(conn, paper: dict) -> bool:
    """检查论文是否已存在（按 arxiv_id 或 paper_url 去重）。"""
    if paper.get("arxiv_id"):
        row = conn.execute(
            "SELECT id FROM papers WHERE arxiv_id = ?", (paper["arxiv_id"],)
        ).fetchone()
        if row:
            return True

    if paper.get("paper_url"):
        row = conn.execute(
            "SELECT id FROM papers WHERE paper_url = ?", (paper["paper_url"],)
        ).fetchone()
        if row:
            return True

    return False


def _insert_paper(conn, paper: dict, source_id: int):
    """插入论文到工作区DB。"""
    conn.execute(
        """INSERT INTO papers
           (title, authors, abstract, journal_name, publish_year,
            arxiv_id, paper_url, has_code, code_url,
            auto_keywords, auto_technologies, ai_analyzed)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
        (
            paper.get("title", ""),
            paper.get("authors", "[]"),
            paper.get("abstract", ""),
            paper.get("journal_name", ""),
            paper.get("publish_year"),
            paper.get("arxiv_id"),
            paper.get("paper_url"),
            int(paper.get("has_code", False)),
            paper.get("code_url"),
            paper.get("auto_keywords", "[]"),
            paper.get("auto_technologies", "[]"),
        ),
    )
