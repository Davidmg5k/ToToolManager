from app.router.api.user import user_router
from app.router.api.order import order_router
from app.router.api.auth import auth_router
from app.router.api.inventory import inventory_router
from app.router.api.payment import payment_router
from app.router.api.notification import notification_router
from app.router.api.chat import chat_router

api_routers = [
    user_router,
    order_router,
    auth_router,
    inventory_router,
    payment_router,
    notification_router,
    chat_router,
]
