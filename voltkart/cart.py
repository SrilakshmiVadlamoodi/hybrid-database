import threading

_carts: dict[int, dict[int, int]] = {}
_lock = threading.Lock()


def get_cart(customer_id: int) -> dict[int, int]:
    with _lock:
        return dict(_carts.get(customer_id, {}))


def add_to_cart(customer_id: int, product_id: int, qty: int) -> None:
    with _lock:
        cart = _carts.setdefault(customer_id, {})
        cart[product_id] = cart.get(product_id, 0) + qty


def take_cart(customer_id: int) -> dict[int, int]:
    """Atomically remove and return a customer's cart, so a concurrent
    checkout request sees it empty instead of racing on the same items."""
    with _lock:
        return _carts.pop(customer_id, {})


def restore_cart(customer_id: int, cart: dict[int, int]) -> None:
    """Put items back after a failed checkout, merging with anything added since."""
    with _lock:
        existing = _carts.setdefault(customer_id, {})
        for product_id, qty in cart.items():
            existing[product_id] = existing.get(product_id, 0) + qty


def clear_cart(customer_id: int) -> None:
    with _lock:
        _carts.pop(customer_id, None)
