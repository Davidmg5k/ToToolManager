from uuid import UUID

from app.service import ChatService, ChatSessionRepository, ChatMessageRepository
from app.types.chat import CreateChatSession, CreateChatMessage, GetChatSession, UpdateChatSession, UpdateChatSessionStatus


class ChatController:

    def __init__(self, session_repo: ChatSessionRepository, message_repo: ChatMessageRepository) -> None:
        self.__service = ChatService(session_repo, message_repo)

    async def create_session(self, data: CreateChatSession):
        return await self.__service.create_session(data)

    async def get_session(self, chat_id: UUID):
        return await self.__service.get_session(GetChatSession(chat_id=chat_id))

    async def list_sessions(self):
        return await self.__service.list_sessions()

    async def update_session_title(self, chat_id: UUID, title: str):
        return await self.__service.update_session_title(UpdateChatSession(chat_id=chat_id, title=title))

    async def update_session_status(self, chat_id: UUID, is_processing: bool):
        return await self.__service.update_session_status(
            UpdateChatSessionStatus(chat_id=chat_id, is_processing=is_processing)
        )

    async def delete_session(self, chat_id: UUID):
        return await self.__service.delete_session(GetChatSession(chat_id=chat_id))

    async def add_message(self, data: CreateChatMessage):
        return await self.__service.add_message(data)

    async def get_messages(self, chat_id: UUID):
        return await self.__service.get_messages(GetChatSession(chat_id=chat_id))

    async def count_messages(self, chat_id: UUID) -> int:
        return await self.__service.count_messages(GetChatSession(chat_id=chat_id))
