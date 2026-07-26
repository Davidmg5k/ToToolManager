from typing import Any, Generic, Sequence, TypeVar
from uuid import UUID

from sqlmodel import Session, SQLModel, select

ModelT = TypeVar("ModelT", bound=SQLModel)


class Repository(Generic[ModelT]):
    """Generic SQLModel repository providing CRUD operations.

    Subclass this for each entity to add domain-specific queries.
    """

    def __init__(self, session: Session, model: type[ModelT]) -> None:
        self._session = session
        self._model = model

    @property
    def _pk_field(self) -> str:
        """Auto-detect the primary key field name from the model."""
        for key in self._model.model_fields:
            field_info = self._model.model_fields[key]
            if getattr(field_info, "primary_key", False):
                return key
        raise ValueError(f"No primary key found in {self._model.__name__}")

    def get(self, id: UUID) -> ModelT | None:
        pk = self._pk_field
        statement = select(self._model).where(getattr(self._model, pk) == id)
        return self._session.exec(statement).first()

    def get_or_raise(self, id: UUID, entity: str | None = None) -> ModelT:
        from app.exception import NotFoundException

        obj = self.get(id)
        if obj is None:
            raise NotFoundException(entity or self._model.__name__, id)
        return obj

    def create(self, data: SQLModel) -> ModelT:
        obj = self._model.model_validate(data)
        self._session.add(obj)
        self._session.commit()
        self._session.refresh(obj)
        return obj

    def update(self, id: UUID, data: dict[str, Any]) -> ModelT:
        obj = self.get_or_raise(id)
        for key, value in data.items():
            if value is not None:
                setattr(obj, key, value)
        self._session.add(obj)
        self._session.commit()
        self._session.refresh(obj)
        return obj

    def delete(self, id: UUID) -> None:
        obj = self.get_or_raise(id)
        self._session.delete(obj)
        self._session.commit()

    def list_all(self) -> Sequence[ModelT]:
        statement = select(self._model)
        return self._session.exec(statement).all()

    def find_by(self, **kwargs: Any) -> ModelT | None:
        statement = select(self._model)
        for key, value in kwargs.items():
            statement = statement.where(getattr(self._model, key) == value)
        return self._session.exec(statement).first()

    def list_where(self, **kwargs: Any) -> Sequence[ModelT]:
        statement = select(self._model)
        for key, value in kwargs.items():
            statement = statement.where(getattr(self._model, key) == value)
        return self._session.exec(statement).all()

    def exists(self, **kwargs: Any) -> bool:
        return self.find_by(**kwargs) is not None


class UserRepository(Repository):
    """Repository for User entities."""

    def __init__(self, session: Session) -> None:
        from app.model import User

        super().__init__(session, User)

    def find_by_email(self, email: str) -> Any | None:
        return self.find_by(email=email)


class OrderRepository(Repository):
    """Repository for Order entities."""

    def __init__(self, session: Session) -> None:
        from app.model import Order

        super().__init__(session, Order)

    def list_by_user(self, user_id: UUID) -> Sequence:
        return self.list_where(user_id=user_id)

    def update_status(self, id: UUID, status: str):
        return self.update(id, {"status": status})


class ProductRepository(Repository):
    """Repository for Product entities."""

    def __init__(self, session: Session) -> None:
        from app.model import Product

        super().__init__(session, Product)

    def update_stock(self, id: UUID, stock: int):
        return self.update(id, {"stock": stock})

    def list_below_stock(self, threshold: int = 10) -> Sequence:
        statement = select(self._model).where(self._model.stock <= threshold)
        return self._session.exec(statement).all()


class PaymentRepository(Repository):
    """Repository for PaymentRecord entities."""

    def __init__(self, session: Session) -> None:
        from app.model import PaymentRecord

        super().__init__(session, PaymentRecord)

    def list_by_order(self, order_id: UUID) -> Sequence:
        return self.list_where(order_id=order_id)

    def update_status(self, id: UUID, status):
        return self.update(id, {"status": status})


class NotificationRepository(Repository):
    """Repository for NotificationRecord entities."""

    def __init__(self, session: Session) -> None:
        from app.model import NotificationRecord

        super().__init__(session, NotificationRecord)

    def list_by_user(self, user_id: UUID) -> Sequence:
        return self.list_where(user_id=user_id)

    def update_status(self, id: UUID, status):
        return self.update(id, {"status": status})
