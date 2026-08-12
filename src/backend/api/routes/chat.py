"""Workspace-local, audited multi-turn paper chat API."""
from typing import Annotated

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services import chat_service


router = APIRouter()
PaperId = Annotated[int, Field(strict=True, gt=0)]


class ChatSessionCreate(BaseModel):
    title: str = Field("新对话", min_length=1, max_length=80)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10_000)
    paper_ids: list[PaperId] = Field(
        default_factory=list, max_length=chat_service.MAX_PAPERS
    )


@router.get("/chat/sessions")
def list_chat_sessions():
    return chat_service.list_sessions()


@router.post("/chat/sessions")
def create_chat_session(body: ChatSessionCreate = ChatSessionCreate()):
    return chat_service.create_session(body.title.strip())


@router.get("/chat/sessions/{session_id}")
def get_chat_session(session_id: int):
    session = chat_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="聊天会话不存在")
    return session


@router.post("/chat/sessions/{session_id}/turns")
async def create_chat_turn(session_id: int, body: ChatRequest):
    try:
        turn = await chat_service.create_turn(
            session_id,
            message=body.message.strip(),
            paper_ids=body.paper_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not turn:
        raise HTTPException(status_code=404, detail="聊天会话不存在")
    return turn


@router.post("/chat")
async def legacy_chat(body: ChatRequest):
    """Compatibility endpoint; new UI uses explicit persistent sessions."""
    session = chat_service.create_session()
    turn = await chat_service.create_turn(
        session["id"], message=body.message.strip(), paper_ids=body.paper_ids
    )
    return {
        "reply": turn.get("assistant_message") or turn.get("error_message"),
        "error": turn["status"] == "failed",
        "session_id": session["id"],
        "turn": turn,
    }
