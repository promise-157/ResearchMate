"""文档服务 — 读取 docs/ 目录下的 markdown 文件。"""
from pathlib import Path
from fastapi import APIRouter, HTTPException

router = APIRouter()

DOCS_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "docs"


@router.get("/docs/{name}")
def get_doc(name: str):
    """返回指定文档的 markdown 内容。"""
    # 安全检查：防止路径穿越
    if ".." in name or "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail="Invalid doc name")

    file_path = DOCS_DIR / f"{name}.md"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Document not found")

    content = file_path.read_text(encoding="utf-8")
    return {"name": name, "content": content}
