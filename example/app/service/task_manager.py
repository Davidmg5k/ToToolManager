import asyncio
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlmodel import Session

from app import engine
from app.types.chat import ChatTaskStatus, CreateChatMessage

logger = logging.getLogger(__name__)


class _ChatTask:
    __slots__ = (
        "task_id", "chat_id", "status", "created_at",
        "completed_at", "error", "_async_task", "_queues",
    )

    def __init__(self, task_id: str, chat_id: UUID) -> None:
        self.task_id = task_id
        self.chat_id = chat_id
        self.status = ChatTaskStatus.PENDING
        self.created_at = datetime.utcnow()
        self.completed_at: datetime | None = None
        self.error: str | None = None
        self._async_task: asyncio.Task | None = None
        self._queues: list[asyncio.Queue] = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "chat_id": str(self.chat_id),
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
        }


class ChatTaskManager:
    _instance: "ChatTaskManager | None" = None

    def __new__(cls) -> "ChatTaskManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._active: dict[str, _ChatTask] = {}
            cls._instance._lock = asyncio.Lock()
        return cls._instance

    def is_running(self, chat_id: UUID) -> bool:
        key = str(chat_id)
        task = self._active.get(key)
        return task is not None and task.status in (
            ChatTaskStatus.PENDING, ChatTaskStatus.RUNNING
        )

    def get_status(self, chat_id: UUID) -> _ChatTask | None:
        return self._active.get(str(chat_id))

    def subscribe(self, chat_id: UUID) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        key = str(chat_id)
        task = self._active.get(key)
        if task is not None:
            task._queues.append(queue)
        return queue

    def unsubscribe(self, chat_id: UUID, queue: asyncio.Queue) -> None:
        key = str(chat_id)
        task = self._active.get(key)
        if task is not None and queue in task._queues:
            task._queues.remove(queue)

    async def start(
        self,
        chat_id: UUID,
        message: str,
        agent: Any,
        *,
        deps: Any = None,
        title: str | None = None,
    ) -> str:
        key = str(chat_id)

        async with self._lock:
            existing = self._active.get(key)
            if existing is not None and existing.status in (
                ChatTaskStatus.PENDING, ChatTaskStatus.RUNNING
            ):
                raise ValueError(f"Chat {chat_id} already has a running task")

        task_id = f"{key}:{int(datetime.utcnow().timestamp())}"
        task = _ChatTask(task_id, chat_id)
        task.status = ChatTaskStatus.PENDING
        self._active[key] = task

        task._async_task = asyncio.create_task(
            self._run(task, chat_id, message, agent, deps=deps, title=title)
        )
        return task_id

    async def cancel(self, chat_id: UUID) -> bool:
        key = str(chat_id)
        task = self._active.get(key)
        if task is None:
            return False
        if task._async_task is not None and not task._async_task.done():
            task._async_task.cancel()
            try:
                await task._async_task
            except asyncio.CancelledError:
                pass
            task.status = ChatTaskStatus.FAILED
            task.completed_at = datetime.utcnow()
            await self._notify(task)
            self._cleanup_session_flag(chat_id, False)
            return True
        return False

    async def _run(
        self,
        task: _ChatTask,
        chat_id: UUID,
        message: str,
        agent: Any,
        *,
        deps: Any = None,
        title: str | None = None,
    ) -> None:
        task.status = ChatTaskStatus.RUNNING
        self._set_session_flag(chat_id, True)
        await self._notify(task)

        tools_session = Session(engine)
        chat_session = Session(engine)
        full_response_tokens: list[str] = []

        try:
            if title:
                from app.service.resource.repository import ChatSessionRepository
                session_repo = ChatSessionRepository(chat_session)
                session_repo.update(chat_id, {"title": title, "updated_at": datetime.utcnow()})

            stream = agent.run_stream(message, deps=deps)
            async with stream as result:
                async for token in result.stream_text():
                    full_response_tokens.append(token)
                    await self._broadcast_token(task, token)

            full_response = "".join(full_response_tokens)

            from app.service.resource.repository import (
                ChatSessionRepository, ChatMessageRepository,
            )
            msg_repo = ChatMessageRepository(chat_session)
            session_repo = ChatSessionRepository(chat_session)

            msg_repo.create(CreateChatMessage(
                chat_id=chat_id, role="assistant", content=full_response,
            ))
            session_repo.update(chat_id, {
                "updated_at": datetime.utcnow(),
                "is_processing": False,
            })

            task.status = ChatTaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()

        except asyncio.CancelledError:
            task.status = ChatTaskStatus.FAILED
            task.error = "Cancelled"
            task.completed_at = datetime.utcnow()
            self._set_session_flag(chat_id, False)
            raise

        except Exception as exc:
            logger.exception("Background task failed for chat %s", chat_id)
            task.status = ChatTaskStatus.FAILED
            task.error = str(exc)
            task.completed_at = datetime.utcnow()

            try:
                from app.service.resource.repository import (
                    ChatSessionRepository, ChatMessageRepository,
                )
                msg_repo = ChatMessageRepository(chat_session)
                session_repo = ChatSessionRepository(chat_session)

                msg_repo.create(CreateChatMessage(
                    chat_id=chat_id,
                    role="assistant",
                    content=f"[Error] {exc}",
                ))
                session_repo.update(chat_id, {
                    "updated_at": datetime.utcnow(),
                    "is_processing": False,
                })
            except Exception:
                logger.exception("Failed to save error message for chat %s", chat_id)

        finally:
            try:
                tools_session.close()
                chat_session.close()
            except Exception:
                pass

            await self._notify(task)
            await self._broadcast_done(task)

    async def _broadcast_token(self, task: _ChatTask, token: str) -> None:
        for q in list(task._queues):
            try:
                q.put_nowait({"type": "token", "text": token})
            except asyncio.QueueFull:
                pass

    async def _broadcast_done(self, task: _ChatTask) -> None:
        payload = {
            "type": "done",
            "status": task.status.value,
            "error": task.error,
        }
        for q in list(task._queues):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    async def _notify(self, task: _ChatTask) -> None:
        for q in list(task._queues):
            try:
                q.put_nowait({"type": "status", **task.to_dict()})
            except asyncio.QueueFull:
                pass

    def _set_session_flag(self, chat_id: UUID, value: bool) -> None:
        session = Session(engine)
        try:
            from app.model import ChatSession
            from sqlmodel import select
            stmt = select(ChatSession).where(ChatSession.chat_id == chat_id)
            obj = session.exec(stmt).first()
            if obj is not None:
                obj.is_processing = value
                obj.updated_at = datetime.utcnow()
                session.add(obj)
                session.commit()
        except Exception:
            logger.exception("Failed to update session flag for %s", chat_id)
        finally:
            session.close()

    def _cleanup_session_flag(self, chat_id: UUID, value: bool) -> None:
        self._set_session_flag(chat_id, value)


chat_task_manager = ChatTaskManager()
