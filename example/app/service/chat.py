from datetime import datetime

from app.exception import NotFoundException
from app.service.resource.repository import ChatSessionRepository, ChatMessageRepository
from app.types.chat import CreateChatSession, CreateChatMessage, GetChatSession, UpdateChatSession, UpdateChatSessionStatus


class ChatService:

    def __init__(self, session_repo: ChatSessionRepository, message_repo: ChatMessageRepository) -> None:
        self.__session_repo = session_repo
        self.__message_repo = message_repo

    async def create_session(self, data: CreateChatSession):
        return self.__session_repo.create(data)

    async def get_session(self, data: GetChatSession):
        session = self.__session_repo.get(data.chat_id)
        if session is None:
            raise NotFoundException("ChatSession", data.chat_id)
        return session

    async def list_sessions(self):
        return self.__session_repo.list_ordered()

    async def update_session_title(self, data: UpdateChatSession):
        self.__session_repo.get_or_raise(data.chat_id, "ChatSession")
        return self.__session_repo.update(data.chat_id, {"title": data.title, "updated_at": datetime.utcnow()})

    async def update_session_status(self, data: UpdateChatSessionStatus):
        self.__session_repo.get_or_raise(data.chat_id, "ChatSession")
        return self.__session_repo.update(data.chat_id, {
            "is_processing": data.is_processing,
            "updated_at": datetime.utcnow(),
        })

    async def delete_session(self, data: GetChatSession):
        self.__session_repo.get_or_raise(data.chat_id, "ChatSession")
        self.__message_repo.delete_by_chat(data.chat_id)
        self.__session_repo.delete(data.chat_id)
        return {"deleted": True}

    async def add_message(self, data: CreateChatMessage):
        msg = self.__message_repo.create(data)
        self.__session_repo.update(data.chat_id, {"updated_at": datetime.utcnow()})
        return msg

    async def get_messages(self, data: GetChatSession):
        return self.__message_repo.list_by_chat(data.chat_id)

    async def count_messages(self, data: GetChatSession) -> int:
        return self.__message_repo.count_by_chat(data.chat_id)
