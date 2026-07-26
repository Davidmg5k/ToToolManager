from app.router.web.index import web_router
from app.router.web.login import login_router
from app.router.web.dashboard import dashboard_router
from app.router.web.users import users_router
from app.router.web.orders import orders_router
from app.router.web.inventory import inventory_router
from app.router.web.payments import payments_router
from app.router.web.notifications import notifications_router
from app.router.web.chat import chat_router

web_routers = [
    web_router,
    login_router,
    dashboard_router,
    users_router,
    orders_router,
    inventory_router,
    payments_router,
    notifications_router,
    chat_router,
]
