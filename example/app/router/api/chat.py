import json
import asyncio

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from sqlmodel import Session

from app import engine
from app.controller import (
    build_communication_module,
    build_user_service,
    build_order_service,
    build_auth_service,
    build_inventory_service,
    build_payment_service,
    build_notification_service,
    build_commerce_module,
    ChatController,
)
from app.service import ChatSessionRepository, ChatMessageRepository, chat_task_manager
from app.types.chat import CreateChatSession, CreateChatMessage, UpdateChatSession
from app.security.middleware_ai.sanitize import SensitiveFieldMiddlewareAI
from to_tool_manager import ToToolManager
from to_tool_manager.adapters.pydantic_ai import build_agent

chat_router = APIRouter(prefix="/api/chat", tags=["api", "chat"])

MODEL = "groq:openai/gpt-oss-120b"

SYSTEM_PROMPT = (
    "You are a helpful assistant for a commerce application. "
    "You can manage users, orders, products, payments, and notifications. "
    "Rules:\n"
    "- ALWAYS respond in natural, conversational language.\n"
    "- When listing multiple items, use a markdown table for clarity.\n"
    "- When creating/updating/deleting, confirm what was done.\n"
    "- If there is an error, explain it clearly.\n"
    "- Keep responses short and friendly.\n"
    "- Respond in the same language the user writes in."
)


def _get_manager():
    session = Session(engine)
    manager = ToToolManager([
            build_user_service(session),
            build_order_service(session),
            build_auth_service(session),
            build_inventory_service(session),
            build_payment_service(session),
            build_notification_service(session),
            build_commerce_module(session),
            build_communication_module(session),
        ],
        middlewares=[SensitiveFieldMiddlewareAI()]
    )
    return manager, session


def _get_chat_controller():
    session = Session(engine)
    return ChatController(
        ChatSessionRepository(session),
        ChatMessageRepository(session),
    ), session


def _generate_title(message: str, max_length: int = 50) -> str:
    text = message.strip()
    if len(text) <= max_length:
        return text
    truncated = text[:max_length]
    last_space = truncated.rfind(" ")
    if last_space > 20:
        return truncated[:last_space] + "..."
    return truncated + "..."


# --- Session CRUD ---


@chat_router.post("/sessions")
async def create_session(request: Request):
    form = await request.form()
    title = form.get("title", "New Chat")
    controller, db = _get_chat_controller()
    try:
        session_obj = await controller.create_session(CreateChatSession(title=title))
        return JSONResponse(
            content={},
            headers={
                "HX-Trigger": json.dumps({
                    "chatSessionCreated": {
                        "chat_id": str(session_obj.chat_id),
                        "title": session_obj.title,
                    }
                })
            },
        )
    finally:
        db.close()


@chat_router.get("/sessions")
async def list_sessions(request: Request):
    controller, db = _get_chat_controller()
    try:
        sessions = await controller.list_sessions()
        result = []
        for s in sessions:
            count = await controller.count_messages(s.chat_id)
            result.append({
                "chat_id": str(s.chat_id),
                "title": s.title,
                "message_count": count,
                "is_processing": s.is_processing,
            })
        return JSONResponse(content=result)
    finally:
        db.close()


@chat_router.patch("/sessions/{chat_id}")
async def update_session(chat_id: str, request: Request):
    from uuid import UUID
    form = await request.form()
    title = form.get("title", "")
    if not title.strip():
        raise HTTPException(status_code=400, detail="Title cannot be empty")
    controller, db = _get_chat_controller()
    try:
        await controller.update_session_title(UUID(chat_id), title.strip())
        return JSONResponse(
            content={},
            headers={
                "HX-Trigger": json.dumps({"chatSessionUpdated": {"chat_id": chat_id, "title": title.strip()}})
            },
        )
    finally:
        db.close()


@chat_router.delete("/sessions/{chat_id}")
async def delete_session(chat_id: str):
    from uuid import UUID
    controller, db = _get_chat_controller()
    try:
        uid = UUID(chat_id)
        await chat_task_manager.cancel(uid)
        await controller.delete_session(uid)
        return JSONResponse(
            content={},
            headers={
                "HX-Trigger": json.dumps({"chatSessionDeleted": {"chat_id": chat_id}})
            },
        )
    finally:
        db.close()


# --- Chat Messages ---


@chat_router.get("/sessions/{chat_id}/messages")
async def get_messages(chat_id: str):
    from uuid import UUID
    controller, db = _get_chat_controller()
    try:
        messages = await controller.get_messages(UUID(chat_id))
        result = [{"role": msg.role, "content": msg.content} for msg in messages]
        return JSONResponse(content=result)
    finally:
        db.close()


# --- Background chat execution ---


@chat_router.post("/sessions/{chat_id}/send")
async def chat_send(chat_id: str, request: Request):
    from uuid import UUID
    form = await request.form()
    message = form.get("message", "")
    if not message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    uid = UUID(chat_id)
    controller, db = _get_chat_controller()

    try:
        session_obj = await controller.get_session(uid)
        needs_title = session_obj.title == "New Chat"
        new_title = _generate_title(message) if needs_title else None

        await controller.add_message(CreateChatMessage(chat_id=uid, role="user", content=message))

        manager, tools_session = _get_manager()
        agent = build_agent(model=MODEL, manager=manager, system_prompt=SYSTEM_PROMPT)

        try:
            task_id = await chat_task_manager.start(
                chat_id=uid,
                message=message,
                agent=agent,
                title=new_title,
            )
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
        finally:
            tools_session.close()

        return JSONResponse(content={"task_id": task_id, "status": "started"})
    finally:
        db.close()


@chat_router.get("/sessions/{chat_id}/status")
async def chat_status(chat_id: str):
    from uuid import UUID
    uid = UUID(chat_id)
    task = chat_task_manager.get_status(uid)
    if task is None:
        return JSONResponse(content={"status": "idle"})
    return JSONResponse(content=task.to_dict())


@chat_router.get("/sessions/{chat_id}/events")
async def chat_events(chat_id: str):
    from uuid import UUID
    uid = UUID(chat_id)
    queue = chat_task_manager.subscribe(uid)

    async def event_stream():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
                    continue

                event_type = event.get("type", "")

                if event_type == "token":
                    yield f"data: {json.dumps({'type': 'token', 'text': event['text']})}\n\n"

                elif event_type == "done":
                    yield f"data: {json.dumps({'status': event['status'], 'error': event.get('error')})}\n\n"
                    yield "data: [DONE]\n\n"
                    break

                elif event_type == "status":
                    yield f"data: {json.dumps(event)}\n\n"

        finally:
            chat_task_manager.unsubscribe(uid, queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# --- Legacy endpoints (kept for backward compatibility) ---


@chat_router.post("/")
async def chat(request: Request):
    form = await request.form()
    message = form.get("message", "")
    manager, tools_session = _get_manager()
    try:
        agent = build_agent(
            model=MODEL,
            manager=manager,
            system_prompt=SYSTEM_PROMPT,
        )
        result = await agent.run(message)
        return JSONResponse(content={"role": "assistant", "content": result.output})
    finally:
        tools_session.close()
