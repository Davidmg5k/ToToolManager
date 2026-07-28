"""
Ejemplo completo de clases de dominio.

Estas clases demuestran:
- Múltiples servicios con relaciones entre sí
- Diferentes patrones de errores
- Soporte para operaciones batch
- Comportamiento async/sync mixto
"""
from typing import Literal


# =============================================================================
# Excepciones de Dominio
# =============================================================================

class OrderAlreadyExistsError(Exception):
    """Se intenta crear una orden que ya existe."""
    pass


class OrderNotFoundError(Exception):
    """La orden solicitada no existe."""
    pass


class InsufficientStockError(Exception):
    """No hay suficiente stock para la orden."""
    pass


class UserAlreadyExistsError(Exception):
    """El usuario ya está registrado."""
    pass


class UserNotFoundError(Exception):
    """El usuario no existe en el sistema."""
    pass


class ProductNotFoundError(Exception):
    """El producto no existe."""
    pass


class InvalidQuantityError(Exception):
    """La cantidad solicitada no es válida."""
    pass


# =============================================================================
# Servicios de Dominio
# =============================================================================

class Order:
    """
    Gestiona órdenes de clientes: creación, eliminación y listado.

    Patrones de uso:
    - Crear órdenes validando stock
    - Eliminar órdenes existentes
    - Listar órdenes por usuario o todas
    """

    def __init__(self) -> None:
        self.__orders: list[dict] = [
            {"product": "gpu", "quantity": 1, "user": "David"}
        ]

    def create(self, product_name: str, quantity: int = 1, user: str = "default"):
        """
        Crea una nueva orden.

        Args:
            product_name: Nombre del producto a ordenar.
            quantity: Cantidad a ordenar (debe ser > 0).
            user: Usuario que realiza la orden.
        """
        if quantity <= 0:
            raise InvalidQuantityError(f"Quantity must be positive, got {quantity}")

        # Verificar si ya existe una orden para este producto y usuario
        for order in self.__orders:
            if order["product"] == product_name and order["user"] == user:
                raise OrderAlreadyExistsError(
                    f"Order for '{product_name}' by user '{user}' already exists"
                )

        self.__orders.append({
            "product": product_name,
            "quantity": quantity,
            "user": user,
        })
        return f"Order for '{product_name}' (qty: {quantity}) created for user '{user}'"

    def delete(self, product_name: str, user: str = "default"):
        """
        Elimina una orden por producto y usuario.

        Args:
            product_name: Nombre del producto cuya orden se eliminará.
            user: Usuario propietario de la orden.
        """
        for i, order in enumerate(self.__orders):
            if order["product"] == product_name and order["user"] == user:
                self.__orders.pop(i)
                return f"Order for '{product_name}' by user '{user}' deleted"

        raise OrderNotFoundError(
            f"Order for '{product_name}' by user '{user}' not found"
        )

    def get_orders(self, user: str | None = None):
        """
        Retorna órdenes, opcionalmente filtradas por usuario.

        Args:
            user: Si se especifica, retorna solo órdenes de este usuario.
        """
        if user:
            return [o for o in self.__orders if o["user"] == user]
        return list(self.__orders)

    @property
    def order_count(self):
        """Cantidad total de órdenes."""
        return len(self.__orders)


class User:
    """
    Gestiona usuarios del sistema.

    Patrones de uso:
    - Crear/eliminar usuarios
    - Buscar usuarios
    - Verificar existencia
    """

    def __init__(self) -> None:
        self.__users: dict[str, dict] = {
            "David": {"email": "david@example.com", "active": True}
        }

    def create_user(self, user_name: str, email: str = ""):
        """
        Crea un nuevo usuario.

        Args:
            user_name: Nombre del usuario a crear.
            email: Email del usuario (opcional).
        """
        if user_name in self.__users:
            raise UserAlreadyExistsError(f"User '{user_name}' already exists")

        self.__users[user_name] = {"email": email, "active": True}
        return f"User '{user_name}' created successfully"

    async def delete_user(self, user_name: str):
        """
        Elimina un usuario (async para demostrar soporte mixto).

        Args:
            user_name: Nombre del usuario a eliminar.
        """
        if user_name not in self.__users:
            raise UserNotFoundError(f"User '{user_name}' not found")

        del self.__users[user_name]
        return f"User '{user_name}' deleted successfully"

    def get_users(self):
        """Retorna todos los usuarios."""
        return list(self.__users.keys())

    def get_user(self, user_name: str):
        """
        Obtiene información de un usuario.

        Args:
            user_name: Nombre del usuario a buscar.
        """
        if user_name not in self.__users:
            raise UserNotFoundError(f"User '{user_name}' not found")
        return {"name": user_name, **self.__users[user_name]}

    def user_exists(self, user_name: str) -> bool:
        """Verifica si un usuario existe."""
        return user_name in self.__users


class Product:
    """
    Gestiona el catálogo de productos.

    Patrones de uso:
    - Listar productos por categoría
    - Obtener detalles de producto
    - Verificar stock
    """

    def __init__(self, kind: Literal["cars", "home"]):
        self.__kind = kind
        self.__catalog: dict[str, dict] = {
            "dor": {"name": "Door", "stock": 10, "category": "home"},
            "room": {"name": "Room Kit", "stock": 5, "category": "home"},
            "sedan": {"name": "Sedan", "stock": 3, "category": "cars"},
        }

    @property
    def kind(self):
        """Retorna el tipo de producto configurado."""
        return self.__kind

    def list_products(self):
        """Retorna todos los productos disponibles."""
        return list(self.__catalog.keys())

    def get_product(self, product_id: str):
        """
        Obtiene detalles de un producto.

        Args:
            product_id: ID del producto a buscar.
        """
        if product_id not in self.__catalog:
            raise ProductNotFoundError(f"Product '{product_id}' not found")
        return {"id": product_id, **self.__catalog[product_id]}

    def check_stock(self, product_id: str, quantity: int = 1) -> bool:
        """
        Verifica si hay stock suficiente.

        Args:
            product_id: ID del producto.
            quantity: Cantidad requerida.
        """
        if product_id not in self.__catalog:
            raise ProductNotFoundError(f"Product '{product_id}' not found")
        return self.__catalog[product_id]["stock"] >= quantity

    def get_kind_to_product(self, kind: Literal["cars", "home"]):
        """
        Retorna productos filtrados por categoría.

        Args:
            kind: Categoría de productos a filtrar.
        """
        return [
            pid for pid, info in self.__catalog.items()
            if info["category"] == kind
        ]