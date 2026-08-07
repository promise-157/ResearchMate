"""爬取触发 + 状态查询。接入爬虫注册表，实现去重存储。"""
import asyncio
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
    source_errors = []

    try:
        # 获取选中的期刊源
        placeholders = ",".join("?" * len(source_ids))
        sources = conn.execute(
            f"SELECT * FROM journal_sources WHERE id IN ({placeholders})",
            source_ids,
        ).fetchall()
        sources = [dict_from_row(s) for s in sources]

        total_sources = len(sources)
        if total_sources == 0:
            raise ValueError("没有找到可用的期刊源")

        for idx, source in enumerate(sources):
            _status["message"] = f"正在爬取: {source['label'] or source['url']}"
            _status["percentage"] = int((idx / total_sources) * 60)

            # 找到合适的爬虫
            crawler = find_crawler(source["url"])
            if not crawler:
                source_errors.append(source["label"] or source["url"])
                continue

            # 爬取
            try:
                papers = await crawler.crawl(source["url"], mode, keywords, sort_mode)
            except Exception as e:
                print(f"[crawl] error crawling {source['url']}: {e}")
                source_errors.append(source["label"] or source["url"])
                continue

            task_cursor = ws_conn.execute(
                "INSERT INTO crawl_tasks (source_id, keywords, sort_mode, paper_count) VALUES (?, ?, ?, 0)",
                (source["id"], keywords, sort_mode),
            )
            task_id = task_cursor.lastrowid

            # 去重 + 入库；all 模式刷新已有元数据。
            new_count = 0
            for paper in papers:
                if _paper_exists(ws_conn, paper):
                    if mode == "all":
                        _update_paper(ws_conn, paper, source["id"], task_id)
                    continue

                # 关键词自动提取
                from processors.keyword_extractor import extract_for_paper
                kw_data = extract_for_paper(paper)
                paper.update(kw_data)

                paper_id = _insert_paper(ws_conn, paper, source["id"], task_id)
                from services.paper_materials import map_paper_to_material
                if map_paper_to_material(ws_conn, paper_id) is None:
                    raise RuntimeError("论文缺少可映射的标题或摘要")
                new_count += 1
                all_new_papers.append(paper)

            ws_conn.execute(
                "UPDATE crawl_tasks SET paper_count = ? WHERE id = ?",
                (len(papers), task_id),
            )
            ws_conn.commit()

            # 更新期刊源的最后爬取时间
            conn.execute(
                "UPDATE journal_sources SET last_crawled_at = ?, last_paper_count = ? WHERE id = ?",
                (datetime.now().strftime("%Y-%m-%d %H:%M"), len(papers), source["id"]),
            )
            conn.commit()

            # 请求间隔
            from config import get as config_get
            interval = config_get("crawler", "request_interval") or 2
            await asyncio.sleep(interval)

        _status["percentage"] = 100
        if len(source_errors) == total_sources:
            _status["status"] = "error"
            _status["message"] = "所有来源同步失败，请检查来源与网络"
        else:
            _status["status"] = "done"
            suffix = f"，{len(source_errors)} 个来源失败" if source_errors else ""
            _status["message"] = f"同步完成，新增 {len(all_new_papers)} 篇{suffix}"

        # 更新主DB工作区计数
        from storage.workspace import get_active_path
        paper_count = ws_conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
        item_count = ws_conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        conn.execute(
            "UPDATE workspaces SET paper_count = ?, item_count = ? WHERE db_path = ?",
            (paper_count, item_count, get_active_path()),
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


def _insert_paper(conn, paper: dict, source_id: int, task_id: int):
    """插入论文到工作区DB。"""
    cursor = conn.execute(
        """INSERT INTO papers
           (task_id, source_id, title, authors, abstract, journal_name, publish_year,
            arxiv_id, paper_url, has_code, code_url,
            auto_keywords, auto_technologies, ai_analyzed)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
        (
            task_id,
            source_id,
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
    return cursor.lastrowid


def _update_paper(conn, paper: dict, source_id: int, task_id: int):
    """Refresh source metadata without overwriting user or AI state."""
    from processors.keyword_extractor import extract_for_paper

    paper.update(extract_for_paper(paper))
    identity_column = "arxiv_id" if paper.get("arxiv_id") else "paper_url"
    identity = paper.get(identity_column)
    if not identity:
        return
    conn.execute(
        f"""UPDATE papers SET
            task_id = ?, source_id = ?, title = ?, authors = ?, abstract = ?,
            journal_name = ?, publish_year = ?, paper_url = ?, has_code = MAX(has_code, ?),
            code_url = COALESCE(?, code_url), auto_keywords = ?, auto_technologies = ?
            WHERE {identity_column} = ?""",
        (
            task_id, source_id, paper.get("title", ""), paper.get("authors", "[]"),
            paper.get("abstract", ""), paper.get("journal_name", ""),
            paper.get("publish_year"), paper.get("paper_url"),
            int(paper.get("has_code", False)), paper.get("code_url"),
            paper.get("auto_keywords", "[]"), paper.get("auto_technologies", "[]"),
            identity,
        ),
    )
