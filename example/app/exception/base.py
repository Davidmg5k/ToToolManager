from uuid import UUID


class AppException(Exception):
    """Base exception for all application domain errors."""

    def __init__(self, message: str = "", detail: dict | None = None) -> None:
        self.message = message
        self.detail = detail or {}
        super().__init__(self.message)


class NotFoundException(AppException):
    """Raised when a requested entity does not exist."""

    def __init__(self, entity: str, identifier: UUID | str) -> None:
        super().__init__(
            message=f"{entity} with id '{identifier}' not found",
            detail={"entity": entity, "identifier": str(identifier)},
        )


class AlreadyExistsException(AppException):
    """Raised when trying to create an entity that already exists."""

    def __init__(self, entity: str, field: str, value: str) -> None:
        super().__init__(
            message=f"{entity} with {field} '{value}' already exists",
            detail={"entity": entity, "field": field, "value": value},
        )


class ValidationException(AppException):
    """Raised when input data fails business validation."""

    def __init__(self, message: str, field: str | None = None) -> None:
        detail = {"field": field} if field else {}
        super().__init__(message=message, detail=detail)


class UnauthorizedException(AppException):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(message=message)


class ForbiddenException(AppException):
    """Raised when the user lacks permission for the requested action."""

    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(message=message)


class ConflictException(AppException):
    """Raised when an operation conflicts with the current entity state."""

    def __init__(self, message: str, detail: dict | None = None) -> None:
        super().__init__(message=message, detail=detail)


class PaymentFailedException(AppException):
    """Raised when a payment processing operation fails."""

    def __init__(self, message: str, provider: str | None = None) -> None:
        detail = {"provider": provider} if provider else {}
        super().__init__(message=message, detail=detail)


class InsufficientStockException(AppException):
    """Raised when there is not enough stock for the requested operation."""

    def __init__(self, product_id: UUID, requested: int, available: int) -> None:
        super().__init__(
            message=(
                f"Insufficient stock for product '{product_id}': "
                f"requested {requested}, available {available}"
            ),
            detail={
                "product_id": str(product_id),
                "requested": requested,
                "available": available,
            },
        )


class NotificationDeliveryException(AppException):
    """Raised when a notification fails to be delivered."""

    def __init__(self, channel: str, recipient: str, reason: str = "") -> None:
        message = f"Failed to deliver notification via {channel} to '{recipient}'"
        if reason:
            message += f": {reason}"
        super().__init__(
            message=message,
            detail={"channel": channel, "recipient": recipient, "reason": reason},
        )
