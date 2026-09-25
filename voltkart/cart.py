_carts: dict[int, dict[int, int]] = {}


def get_cart(customer_id: int) -> dict[int, int]:
    return _carts.setdefault(customer_id, {})


def add_to_cart(customer_id: int, product_id: int, qty: int) -> None:
    cart = get_cart(customer_id)
    cart[product_id] = cart.get(product_id, 0) + qty


def clear_cart(customer_id: int) -> None:
    _carts.pop(customer_id, None)
