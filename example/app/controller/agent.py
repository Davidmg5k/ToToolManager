from pydantic import ValidationError
from app.security.middleware_ai.sanitize import RemoverPasswordsMiddlewareAI
from app.security.middleware_ai.error_mapper import DomainErrorMappingMiddleware
from to_tool_manager import Service, Module

from app.service import (
    UserService,
    OrderService,
    AuthService,
    InventoryService,
    PaymentService,
    NotificationService,
    UserRepository,
    OrderRepository,
    ProductRepository,
    PaymentRepository,
    NotificationRepository,
)
from app.exception import (
    AlreadyExistsException,
    ConflictException,
    InsufficientStockException,
    NotFoundException,
    NotificationDeliveryException,
    PaymentFailedException,
    UnauthorizedException,
    ValidationException,
)


def build_user_service(session) -> Service:
    repo = UserRepository(session)
    return Service(
        name="user_service",
        service=UserService,
        instructions="Manages user accounts: create, retrieve, update, and delete users.",
        middleware=[
            DomainErrorMappingMiddleware(
                {
                    NotFoundException: "not_found",
                    AlreadyExistsException: "already_exists",
                    ValidationException: "validation_error",
                    ValidationError: "validation_error",
                },
                retryable={ValidationException, ValidationError},
            ),
            RemoverPasswordsMiddlewareAI(include=["get_user"]),
        ],
        args=(repo,),
    )


def build_order_service(session) -> Service:
    repo = OrderRepository(session)
    return Service(
        name="order_service",
        service=OrderService,
        instructions="Manages customer orders: create, update, cancel, and query orders.",
        middleware=[DomainErrorMappingMiddleware(
            {
                NotFoundException: "not_found",
                ConflictException: "conflict",
                ValidationException: "validation_error",
            },
            retryable={ValidationException},
        )],
        args=(repo,),
    )


def build_auth_service(session) -> Service:
    repo = UserRepository(session)
    return Service(
        name="auth_service",
        service=AuthService,
        instructions="Handles authentication: login, token refresh, and token validation.",
        middleware=[DomainErrorMappingMiddleware(
            {
                UnauthorizedException: "unauthorized",
                ValidationException: "validation_error",
            },
            retryable={ValidationException},
        )],
        args=(repo,),
    )


def build_inventory_service(session) -> Service:
    repo = ProductRepository(session)
    return Service(
        name="inventory_service",
        service=InventoryService,
        instructions="Manages product inventory: products, stock levels, and stock adjustments.",
        middleware=[DomainErrorMappingMiddleware(
            {
                NotFoundException: "not_found",
                InsufficientStockException: "insufficient_stock",
                ValidationException: "validation_error",
            },
            retryable={InsufficientStockException, ValidationException},
        )],
        args=(repo,),
    )


def build_payment_service(session) -> Service:
    repo = PaymentRepository(session)
    order_repo = OrderRepository(session)
    return Service(
        name="payment_service",
        service=PaymentService,
        instructions="Processes payments: create, refund, and query payment records.",
        middleware=[DomainErrorMappingMiddleware(
            {
                NotFoundException: "not_found",
                PaymentFailedException: "payment_failed",
                ConflictException: "conflict",
                ValidationException: "validation_error",
            },
            retryable={PaymentFailedException, ValidationException},
        )],
        args=(repo, order_repo),
    )


def build_notification_service(session) -> Service:
    repo = NotificationRepository(session)
    return Service(
        name="notification_service",
        service=NotificationService,
        instructions="Sends notifications via email, SMS, or push channels.",
        middleware=[DomainErrorMappingMiddleware(
            {
                NotFoundException: "not_found",
                NotificationDeliveryException: "delivery_failed",
                ValidationException: "validation_error",
            },
            retryable={NotificationDeliveryException, ValidationException},
        )],
        args=(repo,),
    )


def build_commerce_module(session) -> Module:
    return Module(
        name="commerce",
        description=(
            "Commerce sub-agent: manages products, orders, and payments. "
            "Use this module when the user's request involves creating or "
            "modifying products, placing orders, processing payments, or "
            "querying commerce-related data."
        ),
        system_prompt=(
            "You are a commerce specialist. You can manage products, "
            "process orders, and handle payments. Always ensure stock "
            "availability before confirming orders and validate payment "
            "amounts match order totals."
        ),
        services=[
            build_inventory_service(session),
            build_order_service(session),
            build_payment_service(session),
        ],
    )


def build_communication_module(session) -> Module:
    return Module(
        name="communication",
        description=(
            "Communication sub-agent: handles user notifications and "
            "authentication. Use this module for sending notifications, "
            "managing user sessions, or validating access."
        ),
        system_prompt=(
            "You are a communication specialist. You handle user "
            "notifications across multiple channels and manage "
            "authentication tokens. Ensure notifications are delivered "
            "to the correct recipient via the appropriate channel."
        ),
        services=[
            build_notification_service(session),
            build_auth_service(session),
        ],
    )