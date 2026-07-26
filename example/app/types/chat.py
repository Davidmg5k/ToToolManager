from sqlmodel import SQLModel


class ChatMessage(SQLModel):
    message: str


class ChatResponse(SQLModel):
    reply: str
    tools_called: list[str] = []
