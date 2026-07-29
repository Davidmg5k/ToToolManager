from app.router.api.user import user_router
from app.router.api.order import order_router
from app.router.api.auth import auth_router
from app.router.api.inventory import inventory_router
from app.router.api.payment import payment_router
from app.router.api.notification import notification_router
from app.router.api.chat import chat_router
from app.router.api.dashboard import dashboard_router
from app.router.api.meta import meta_router

api_routers = [
    user_router,
    order_router,
    auth_router,
    inventory_router,
    payment_router,
    notification_router,
    chat_router,
    dashboard_router,
    meta_router,
]
