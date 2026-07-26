from to_tool_manager import Service, Module, ErrorMap

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
        description="Manages user accounts: create, retrieve, update, and delete users.",
        error_map=(
            ErrorMap()
            .map(NotFoundException, category="not_found")
            .map(AlreadyExistsException, category="already_exists")
            .map(ValidationException, category="validation_error", retryable=True)
        ),
        args=(repo,),
        singleton=True,
    )


def build_order_service(session) -> Service:
    repo = OrderRepository(session)
    return Service(
        name="order_service",
        service=OrderService,
        description="Manages customer orders: create, update, cancel, and query orders.",
        error_map=(
            ErrorMap()
            .map(NotFoundException, category="not_found")
            .map(ConflictException, category="conflict")
            .map(ValidationException, category="validation_error", retryable=True)
        ),
        args=(repo,),
        singleton=True,
    )


def build_auth_service(session) -> Service:
    repo = UserRepository(session)
    return Service(
        name="auth_service",
        service=AuthService,
        description="Handles authentication: login, token refresh, and token validation.",
        error_map=(
            ErrorMap()
            .map(UnauthorizedException, category="unauthorized")
            .map(ValidationException, category="validation_error", retryable=True)
        ),
        args=(repo,),
        singleton=True,
    )


def build_inventory_service(session) -> Service:
    repo = ProductRepository(session)
    return Service(
        name="inventory_service",
        service=InventoryService,
        description="Manages product inventory: products, stock levels, and stock adjustments.",
        error_map=(
            ErrorMap()
            .map(NotFoundException, category="not_found")
            .map(InsufficientStockException, category="insufficient_stock")
            .map(ValidationException, category="validation_error", retryable=True)
        ),
        args=(repo,),
        singleton=True,
    )


def build_payment_service(session) -> Service:
    repo = PaymentRepository(session)
    order_repo = OrderRepository(session)
    return Service(
        name="payment_service",
        service=PaymentService,
        description="Processes payments: create, refund, and query payment records.",
        error_map=(
            ErrorMap()
            .map(NotFoundException, category="not_found")
            .map(PaymentFailedException, category="payment_failed", retryable=True)
            .map(ConflictException, category="conflict")
            .map(ValidationException, category="validation_error", retryable=True)
        ),
        args=(repo, order_repo),
        singleton=True,
    )


def build_notification_service(session) -> Service:
    repo = NotificationRepository(session)
    return Service(
        name="notification_service",
        service=NotificationService,
        description="Sends notifications via email, SMS, or push channels.",
        error_map=(
            ErrorMap()
            .map(NotFoundException, category="not_found")
            .map(NotificationDeliveryException, category="delivery_failed", retryable=True)
            .map(ValidationException, category="validation_error", retryable=True)
        ),
        args=(repo,),
        singleton=True,
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
