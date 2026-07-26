import json

import markdown
from fastapi import APIRouter,Request
from fastapi.responses import HTMLResponse
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
    build_commerce_module
)
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
    with Session(engine) as session:
        return ToToolManager([
            build_user_service(session),
            build_order_service(session),
            build_auth_service(session),
            build_inventory_service(session),
            build_payment_service(session),
            build_notification_service(session),
            build_commerce_module(session),
            build_communication_module(session)
        ])


def _ai_bubble(text: str) -> str:
    html = markdown.markdown(text, extensions=["tables", "fenced_code"])
    return (
        '<div class="flex justify-start">'
        '<div class="bg-gray-100 rounded-lg px-4 py-2 max-w-lg ai-bubble">'
        f'{html}'
        '</div></div>'
    )


@chat_router.post("/")
async def chat(request: Request):
    form = await request.form()
    message = form.get("message", "")
    manager = _get_manager()
    agent = build_agent(
        model=MODEL,
        manager=manager,
        system_prompt=SYSTEM_PROMPT,
    )
    result = await agent.run(message)
    return HTMLResponse(content=_ai_bubble(result.output))


@chat_router.post("/stream")
async def chat_stream(request: Request):
    from fastapi.responses import StreamingResponse

    form = await request.form()
    message = form.get("message", "")
    manager = _get_manager()
    agent = build_agent(
        model=MODEL,
        manager=manager,
        system_prompt=SYSTEM_PROMPT,
    )

    async def event_stream():
        async with agent.run_stream(message) as stream:
            async for text in stream.stream_text():
                yield f"data: {json.dumps({'text': text})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
